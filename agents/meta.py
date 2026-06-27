"""MetaAgent: the self-improvement agent. During idle time it reviews recent
performance, lessons, and capability gaps, and AUTHORS a new specialist agent as a
markdown briefing file. The loader picks it up next cycle. It can also disable an
agent that has been consistently unreliable.

Guardrails: validates the briefing parses, refuses reserved/duplicate names,
respects the max_dynamic_agents cap, and only registers tools that actually exist.
"""

from __future__ import annotations

import re

from agents.base import BaseAgent
from agents.briefing_loader import RESERVED, briefings_dir, discover
from agents.dynamic import load_briefing, parse_briefing
from agents.memory_agent import MemoryAgent
from core.blackboard import Blackboard
from core.config import settings
from models_adapter.base import Message
from models_adapter.router import ModelRouter
from tools.registry import ToolRegistry

_SYSTEM = (
    "You are the MetaAgent. You improve the fund by designing NEW specialist research "
    "agents when you spot a capability gap. You output a single agent briefing as a "
    "markdown file: YAML frontmatter then a body that is the agent's system prompt."
)


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)[:48] or "Agent"


class MetaAgent(BaseAgent):
    name = "MetaAgent"

    def __init__(self, bb: Blackboard, router: ModelRouter, tools: ToolRegistry,
                 memory: MemoryAgent) -> None:
        super().__init__(bb, router, tools)
        self.memory = memory

    async def run(self, cycle_id: str):
        from schemas import Confidence
        return self.make_report(cycle_id, topic="meta", summary="MetaAgent runs in idle.",
                                confidence=Confidence(score=0.3, low=0.2, high=0.4), stance="uncertain")

    async def improve(self) -> dict:
        if not settings().get("agents", {}).get("allow_meta", True):
            return {"ok": False, "reason": "meta disabled"}
        existing = discover()
        cap = int(settings().get("agents", {}).get("max_dynamic_agents", 8))
        if len(existing) >= cap:
            return {"ok": False, "reason": f"at dynamic-agent cap ({cap})"}

        available_tools = sorted(self.tools.available())
        existing_names = [b.name for b in existing]
        lessons = self.memory.lessons_context("capability gap missing analysis what to research")

        user = (
            f"Existing custom agents: {existing_names or 'none'}.\n"
            f"Reserved core agents (do NOT duplicate): {sorted(RESERVED)}.\n"
            f"Tools the new agent may use (use ONLY these names): {available_tools}.\n"
            f"Recent lessons / gaps:\n{lessons}\n\n"
            "Design ONE new specialist research agent that fills a real gap (e.g. a "
            "sector, region, data angle, or strategy not yet covered). Output ONLY a "
            "markdown briefing, exactly this shape:\n"
            "---\n"
            "name: <UniqueAgentName>\n"
            "profile: default\n"
            "schedule: cycle\n"
            "enabled: true\n"
            "tools:\n"
            "  - name: <tool from the allowed list>\n"
            "    params: {<param>: <value>}\n"
            "---\n"
            "<system prompt: who this agent is, what it analyzes, its evidence discipline>\n"
            "No prose outside the briefing. No code fences."
        )
        text = await self.router.complete(self.name, [Message("system", self.sys(_SYSTEM)), Message("user", user)])
        meta, body = parse_briefing(text)
        name = str(meta.get("name") or "").strip()

        if not name or not body:
            return {"ok": False, "reason": "model produced no valid briefing"}
        if name in RESERVED or name in existing_names:
            return {"ok": False, "reason": f"name '{name}' reserved or already exists"}

        # keep only tools that actually exist
        good_tools = [t for t in (meta.get("tools") or [])
                      if isinstance(t, dict) and t.get("name") in available_tools]
        meta["tools"] = good_tools
        meta.setdefault("schedule", "cycle")
        meta.setdefault("enabled", True)
        meta["name"] = name

        import yaml
        content = "---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n" + body.strip() + "\n"
        path = briefings_dir() / f"{_slug(name)}.md"
        path.write_text(content, encoding="utf-8")

        # validate it loads; if not, remove it
        if load_briefing(path) is None:
            path.unlink(missing_ok=True)
            return {"ok": False, "reason": "authored briefing failed validation"}

        self.memory.write_lesson(
            title=f"MetaAgent created agent: {name}",
            body=f"New specialist '{name}' with tools {[t['name'] for t in good_tools]}. {body[:200]}",
            outcome="unknown")
        self.log.info("meta_created_agent", name=name, tools=[t["name"] for t in good_tools])
        return {"ok": True, "name": name, "path": str(path), "tools": [t["name"] for t in good_tools]}

    async def author_skill(self) -> dict:
        """Codify a PROVEN, generalizable procedure into a reusable skill playbook so the
        knowledge compounds across every agent (the 'learn from what works' loop). Only
        fires when the lessons reveal a genuinely repeatable pattern worth passing on."""
        if not settings().get("agents", {}).get("allow_meta", True):
            return {"ok": False, "reason": "meta disabled"}
        try:
            skills_now = (await self.tools.call(self.name, "list_skills"))[0].get("skills", [])
        except Exception:
            skills_now = []
        lessons = self.memory.lessons_context(
            "what worked: a profitable or correct analysis pattern, method, or signal worth reusing")
        user = (
            f"Existing skill playbooks (do NOT duplicate; you MAY improve one by reusing its exact "
            f"name): {skills_now}\n\n"
            f"Recent lessons / outcomes of what the fund tried:\n{lessons}\n\n"
            "If — and ONLY if — these reveal a GENERALIZABLE, repeatable procedure that would make "
            "future research/decisions better (not a one-off trade), write it as a concise reusable "
            "playbook: numbered steps, which tools to use, what evidence to demand, common pitfalls. "
            'Return ONLY JSON: {"name": "<short-skill-name>", "rationale": "<why it generalizes>", '
            '"skill": "<the playbook markdown body>"}. If nothing generalizes yet, return '
            '{"name": ""}. Never invent results; base it on what actually worked.')
        text = await self.router.complete(self.name, [Message("system", self.sys(_SYSTEM)), Message("user", user)])
        from agents.util import parse_json_block
        parsed = parse_json_block(text) or {}
        name = str(parsed.get("name") or "").strip()
        body = str(parsed.get("skill") or "").strip()
        if not name or len(body) < 80:
            return {"ok": False, "reason": "no generalizable skill to codify yet"}
        res, _rec = await self.tools.call(self.name, "propose_skill", name=name, body=body,
                                          rationale=str(parsed.get("rationale", ""))[:200])
        if res.get("ok"):
            self.memory.write_lesson(title=f"MetaAgent codified skill: {res.get('name')}",
                                     body=str(parsed.get("rationale", ""))[:200], outcome="unknown")
            self.log.info("meta_authored_skill", name=res.get("name"), improved=res.get("improved"))
        return res
