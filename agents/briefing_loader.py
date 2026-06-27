"""Discovers markdown agent briefings and instantiates DynamicAgents. Re-scanned
each cycle so newly authored agents (by the human or the MetaAgent) activate
without a restart.
"""

from __future__ import annotations

from pathlib import Path

from agents.dynamic import Briefing, DynamicAgent, load_briefing
from agents.memory_agent import MemoryAgent
from core.config import ROOT, settings
from core.logging import get_logger
from models_adapter.router import ModelRouter
from tools.registry import ToolRegistry

log = get_logger("briefings")

# Core roster names are reserved — dynamic briefings cannot impersonate them.
RESERVED = {
    "ResearchAgent", "MacroAgent", "FundamentalsAgent", "SentimentAgent", "IpoMnaAgent",
    "AltDataAgent", "QuantAgent", "RiskAgent", "DecisionAgent", "MemoryAgent",
    "QuantResearchAgent", "MetaAgent",
}


def briefings_dir() -> Path:
    d = settings().get("agents", {}).get("dynamic_dir")
    path = Path(d) if d else (ROOT / "agents" / "briefings")
    path.mkdir(parents=True, exist_ok=True)
    return path


def discover() -> list[Briefing]:
    out: list[Briefing] = []
    seen: set[str] = set()
    cap = int(settings().get("agents", {}).get("max_dynamic_agents", 8))
    for path in sorted(briefings_dir().glob("*.md")):
        b = load_briefing(path)
        if not b or not b.enabled or b.schedule == "off":
            continue
        if b.name in RESERVED or b.name in seen:
            log.warning("briefing_skipped", name=b.name, reason="reserved or duplicate")
            continue
        seen.add(b.name)
        out.append(b)
        if len(out) >= cap:
            break
    return out


def build_dynamic_agents(bb, router: ModelRouter, tools: ToolRegistry, memory: MemoryAgent,
                         watchlist: list[str] | None, schedule: str = "cycle",
                         cycle_index: int = 0) -> list[DynamicAgent]:
    agents = []
    for b in discover():
        if b.schedule != schedule:
            continue
        if b.every > 1 and (cycle_index % b.every) != 0:  # periodic agents skip most cycles
            continue
        agents.append(DynamicAgent(b, bb, router, tools, memory, watchlist))
    return agents
