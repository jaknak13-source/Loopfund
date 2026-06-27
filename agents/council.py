"""CouncilAgent: the deliberation stage. After the analysts each produce their
(independent) report, the council makes them actually WORK TOGETHER on the names
that matter — a structured multi-perspective debate so ideas are evaluated from
every angle, deeply, and across time, instead of being judged in one shallow shot.

For the top candidate(s) it runs three turns, each seeing the FULL set of peer
findings (cross-agent information sharing that the blind analyst pass lacks):
  1. BULL — the strongest evidence-based long case, integrating macro + fundamentals
     + sentiment + smart-money flows + quant, across past / present / future.
  2. BEAR — the skeptic's strongest case against, having read the bull.
  3. SYNTHESIS — a judge weighs both, connects cross-angle dots, and lands on
     act-now / DEVELOP-further / pass with what would confirm or refute the thesis.

A promising-but-thin idea gets a 'develop' verdict and is saved as a developing
thesis (kind=research) so it COMPOUNDS across cycles rather than being rejected and
forgotten. The dossier is fed to the DecisionAgent. Bounded LLM calls (top-N
candidates only) so it stays efficient on the serialized local model.
"""

from __future__ import annotations

from agents.base import BaseAgent
from agents.memory_agent import MemoryAgent
from core.blackboard import Blackboard
from core.config import settings
from models_adapter.router import ModelRouter
from tools.registry import ToolRegistry

_BULL_SYS = (
    "You are the fund's BULL advocate in a deliberation. Your JOB is to build the STRONGEST "
    "honest case to OWN this name from the AVAILABLE evidence. You must ALWAYS make the "
    "argument — do NOT refuse, do NOT say you 'cannot ethically' argue, do NOT just list data "
    "gaps. Thin or imperfect evidence is normal; weak/missing data limits SIZE (a small "
    "starter), not whether you reason. The bear and the source-discipline rules handle caution "
    "— your role is the upside. Integrate every angle (macro regime, fundamentals/valuation, "
    "news, sentiment, smart-money flows, quant signal — note: market/quant/SEC data are TRUSTED "
    "first-party feeds, not 'untrusted') and reason across TIME: past, present setup, forward "
    "catalysts. Cite the specific peer findings you rely on. Concrete, not promotional. <=200 words."
)
_BEAR_SYS = (
    "You are the fund's BEAR advocate / skeptic. You have read the bull case. Make the "
    "STRONGEST case AGAINST or for caution: tail risks, what the bull is ignoring, "
    "weak/uncorroborated evidence, valuation, timing, correlation/concentration. "
    "Attack the thesis from angles the bull did not consider. <=200 words."
)
_SYNTH_SYS = (
    "You are the fund's CIO synthesizing a deliberation. You have the bull case, the "
    "bear case, and all agent findings. Weigh them HONESTLY and connect the cross-angle "
    "dots (what do macro + fundamentals + flows + sentiment together imply that no single "
    "one shows?). Frame past/present/future. Then land on ONE of: ACT_NOW (clear, "
    "corroborated, well-timed), DEVELOP (promising but needs specific further evidence — "
    "say exactly what), or PASS (thesis is weak/contradicted). Never reject a real idea "
    "just for being early — route it to DEVELOP. State conviction (low/med/high) and the "
    "single fact that would confirm AND the one that would refute. <=220 words."
)


class CouncilAgent(BaseAgent):
    name = "CouncilAgent"

    def __init__(self, bb: Blackboard, router: ModelRouter, tools: ToolRegistry,
                 memory: MemoryAgent) -> None:
        super().__init__(bb, router, tools)
        self.memory = memory

    async def run(self, cycle_id: str):
        # not part of the analyst pass; invoked via deliberate() before the decision.
        from schemas import Confidence
        return self.make_report(cycle_id, topic="deliberation",
                                summary="CouncilAgent deliberates on top candidates pre-decision.",
                                confidence=Confidence(score=0.3, low=0.2, high=0.4), stance="uncertain")

    def _peer_context(self, reports, asset: str) -> str:
        """Every agent's read that bears on this name — the shared picture the blind
        analyst pass never assembled."""
        lines = []
        for r in reports:
            relevant = (asset in (r.assets or [])) or (not r.assets and r.agent in
                        ("MacroAgent", "ResearchAgent", "QuantAgent", "RiskAgent"))
            if not relevant:
                continue
            sig = ""
            if asset in (r.asset_signals or {}):
                sig = f" signal={r.asset_signals[asset]:+.2f}"
            cites = ", ".join(c.source for c in r.citations[:3] if c.verified)
            lines.append(f"[{r.agent}] {r.stance} conf={r.confidence.score:.2f}{sig}: "
                         f"{r.summary[:220]}" + (f" (sources: {cites})" if cites else ""))
            for f in r.findings[:2]:
                lines.append(f"   - {f}")
        return "\n".join(lines) or "(no specific peer findings on this name)"

    def _cross_agent_digest(self, reports) -> str:
        """A structured summary of EVERY agent's read this cycle (news, fundamentals, quant,
        macro, sentiment, smart-money, valuation, ...), so the deliberation and the decision
        build on the full shared picture instead of each agent's blind silo."""
        lines = []
        for r in sorted(reports, key=lambda r: r.agent):
            head = f"[{r.agent} | {r.topic} | {r.stance} conf={r.confidence.score:.2f}]"
            body = (r.summary or "")[:240]
            keys = "; ".join(r.findings[:2]) if r.findings else ""
            sig = (" signals=" + ", ".join(f"{a}{v:+.2f}" for a, v in
                   list((r.asset_signals or {}).items())[:4])) if r.asset_signals else ""
            lines.append(f"{head} {body}" + (f" | KEY: {keys}" if keys else "") + sig)
        return ("CROSS-AGENT SUMMARIES this cycle (each agent's read — build on these, don't "
                "ignore peers):\n" + "\n".join(lines) if lines else "no peer reports this cycle")

    async def deliberate(self, cycle_id: str, agg: dict, portfolio_summary: str) -> str:
        """Run the multi-perspective debate on the top candidate(s); return a dossier for
        the DecisionAgent. Bounded by decision.council_candidates (default 2)."""
        reports = self.bb.reports_for_cycle(cycle_id)
        digest = self._cross_agent_digest(reports)
        ranked = [(a, s) for a, s in agg.get("ranked", []) if abs(s) > 0.05]
        max_c = int(settings().get("decision", {}).get("council_candidates", 2))
        candidates = [a for a, _ in ranked[:max_c]]
        if not candidates:
            return (f"{digest}\n\nCouncil: no name has a directional signal this cycle — no "
                    "per-name deliberation, but the cross-agent summaries above stand.")

        corr = agg.get("corroboration", {})
        dossiers = []
        for asset in candidates:
            peer = self._peer_context(reports, asset)
            prior = self.memory.recall(f"{asset} thesis valuation catalyst risk", k=3, kind="research")
            prior_txt = "\n".join(f"- {h.title}: {h.body[:160]}" for h in prior) or "none on record"
            base = (f"{digest}\n\nNAME UNDER DELIBERATION: {asset}\nPortfolio: {portfolio_summary}\n"
                    f"Corroborating credible sources for {asset}: {corr.get(asset, 0)}\n"
                    f"All agent findings on {asset}:\n{peer}\n\n"
                    f"Prior research (past work — re-verify, don't trust blindly):\n{prior_txt}")
            bull = await self.think(_BULL_SYS, base)
            bear = await self.think(_BEAR_SYS, f"{base}\n\nBULL CASE:\n{bull}")
            synth = await self.think(
                _SYNTH_SYS, f"{base}\n\nBULL CASE:\n{bull}\n\nBEAR CASE:\n{bear}")
            dossiers.append(f"=== DELIBERATION: {asset} ===\nBULL:\n{bull}\n\nBEAR:\n{bear}\n\n"
                            f"SYNTHESIS:\n{synth}")
            # promising-but-thin -> save a developing thesis so it compounds (not forgotten)
            if "DEVELOP" in synth.upper():
                self.memory.rag.add(_dev_thesis(asset, synth))
            self.log.info("council_deliberated", asset=asset)
        return f"{digest}\n\n" + "\n\n".join(dossiers)


def _dev_thesis(asset: str, synthesis: str):
    import uuid
    from datetime import datetime, timezone
    from schemas import MemoryEntry
    return MemoryEntry(
        id=str(uuid.uuid4()), created_at=datetime.now(timezone.utc), kind="research",
        title=f"Developing thesis: {asset}", body=synthesis[:1500], assets=[asset],
        tags=["developing-thesis", "council", asset])
