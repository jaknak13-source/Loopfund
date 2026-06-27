"""Markdown-defined agents. A briefing file is YAML frontmatter + a body that IS
the agent's system prompt. This lets the system (and the human) add new specialist
agents by dropping a .md file — no code change.

Briefing format (agents/briefings/<name>.md):

    ---
    name: SupplyChainAgent
    profile: default            # default | dev  (which model)
    schedule: cycle             # cycle | idle | off
    enabled: true
    tools:
      - name: gdelt_search
        params: {query: "supply chain disruption port strike", max_records: 10}
      - name: web_search
        params: {query: "semiconductor lead times 2026"}
    ---
    You are the SupplyChainAgent. Track shipping, ports, and input-cost chains...
    (this body becomes the system prompt / briefing)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from agents.analyst import LLMAnalystAgent
from agents.memory_agent import MemoryAgent
from core.blackboard import Blackboard
from models_adapter.router import ModelRouter
from tools.registry import ToolRegistry

VALID_SCHEDULES = {"cycle", "idle", "off"}


@dataclass
class Briefing:
    name: str
    body: str
    profile: str = "default"
    schedule: str = "cycle"
    enabled: bool = True
    every: int = 1            # run every Nth cycle (>1 = periodic, keeps cycles fast)
    tools: list[dict] = field(default_factory=list)
    path: str | None = None


def parse_briefing(text: str) -> tuple[dict, str]:
    """Split frontmatter (---) from body. Returns (meta dict, body str)."""
    t = text.lstrip()
    if t.startswith("---"):
        parts = t.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            return (meta if isinstance(meta, dict) else {}), parts[2].strip()
    return {}, t.strip()


def load_briefing(path: Path) -> Briefing | None:
    try:
        meta, body = parse_briefing(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    name = str(meta.get("name") or path.stem).strip()
    if not name or not body:
        return None
    schedule = str(meta.get("schedule", "cycle"))
    if schedule not in VALID_SCHEDULES:
        schedule = "cycle"
    tools = meta.get("tools") or []
    norm_tools = [
        {"name": str(t.get("name")), "params": dict(t.get("params") or {})}
        for t in tools if isinstance(t, dict) and t.get("name")
    ]
    prof = str(meta.get("profile", "default"))
    try:
        every = max(1, int(meta.get("every", 1)))
    except (TypeError, ValueError):
        every = 1
    return Briefing(
        name=name, body=body,
        profile=prof if prof in ("default", "dev", "creative") else "default",
        schedule=schedule, enabled=bool(meta.get("enabled", True)), every=every,
        tools=norm_tools, path=str(path),
    )


class DynamicAgent(LLMAnalystAgent):
    """An agent whose role/system prompt and data tools come from a briefing file."""

    def __init__(self, briefing: Briefing, bb: Blackboard, router: ModelRouter,
                 tools: ToolRegistry, memory: MemoryAgent, watchlist: list[str] | None = None) -> None:
        super().__init__(bb, router, tools, memory, watchlist)
        self.briefing = briefing
        self.name = briefing.name
        self.role_system = briefing.body
        self.topic = briefing.name.lower()
        self.profile = briefing.profile
        self.log = self.log.bind(agent=self.name) if hasattr(self.log, "bind") else self.log

    async def gather(self, cycle_id: str):
        tool_ids: list[str] = []
        ctx: list[str] = []
        cites: list[dict] = []
        for spec in self.briefing.tools:
            tname = spec["name"]
            if tname not in self.tools.available():
                ctx.append(f"[tool {tname} unavailable]")
                continue
            params = spec.get("params", {})
            # fan a per-ticker tool over the watchlist if a param uses the $WATCHLIST token
            fan_key = next((k for k, v in params.items() if v == "$WATCHLIST"), None)
            param_sets = ([{**params, fan_key: t} for t in self.watchlist[:5]]
                          if fan_key else [params])
            for pset in param_sets:
                try:
                    res, rec = await self.tools.call(self.name, tname, **pset)
                    tool_ids.append(rec.id)
                except Exception as exc:
                    ctx.append(f"[{tname} failed: {type(exc).__name__}]")
                    continue
                ctx.append(f"[{tname}] {_summarize(res)}")
                for a in (res.get("articles") or res.get("results") or [])[:10]:
                    title = a.get("title") or a.get("link")
                    if title:
                        cites.append({"source": a.get("link") or a.get("source", tname),
                                      "claim": title, "verified": False, "primary": False})
        return "\n\n".join(ctx) if ctx else "No tools declared.", tool_ids, cites


def _summarize(res: object) -> str:
    if isinstance(res, dict):
        for k in ("articles", "results", "posts", "messages", "filings"):
            if k in res and isinstance(res[k], list):
                items = res[k][:8]
                return "\n" + "\n".join(
                    f"  - {it.get('title') or it.get('body') or it.get('form') or it}" for it in items
                )
        return str({k: v for k, v in res.items() if k not in ("bars",)})[:1500]
    return str(res)[:1500]
