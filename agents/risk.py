"""RiskAgent: the institutional skeptic. Runs after the other agents, reads their
reports, and attacks the bull case — downside, tails, correlation breaks,
liquidity, concentration. Also provides a rebuttal used in the decision debate.
"""

from __future__ import annotations

from agents.analyst import LLMAnalystAgent
from models_adapter.base import Message


class RiskAgent(LLMAnalystAgent):
    name = "RiskAgent"
    topic = "risk"
    role_system = (
        "You are the RiskAgent, the fund's skeptic. For every thesis, ask: what is "
        "the worst that can happen and how likely is it? Surface tail risks, "
        "correlation breakdowns, liquidity traps, single-event exposure, and "
        "concentration. Penalize unverified claims hard. Default to caution."
    )

    async def gather(self, cycle_id):
        reports = [r for r in self.bb.reports_for_cycle(cycle_id) if r.agent != self.name]
        if not reports:
            return "No peer reports yet this cycle.", [], []
        lines = []
        for r in reports:
            lines.append(
                f"[{r.agent}] stance={r.stance} conf={r.confidence.score:.2f} :: {r.summary[:300]}"
            )
            for u in r.unverified_claims[:3]:
                lines.append(f"   UNVERIFIED: {u}")
        return "Peer reports to stress-test:\n" + "\n".join(lines), [], []

    async def rebut(self, cycle_id: str, candidate_text: str) -> str:
        """Produce a sharp rebuttal of a proposed decision. Plain text."""
        reports = self.bb.reports_for_cycle(cycle_id)
        peer = "\n".join(f"[{r.agent}] {r.stance} ({r.confidence.score:.2f})" for r in reports)
        user = (
            f"House rules:\n{self.house_rules()[:3000]}\n\n"
            f"Peer stances:\n{peer}\n\n"
            f"Proposed decision:\n{candidate_text}\n\n"
            "Attack this decision in <=150 words. Name the single biggest risk. Then "
            "judge per the house rules, which set SIZE by evidence strength (>=2 distinct "
            "credible secondary sources justify a SMALL position; only large/concentrated/"
            "single-event bets need a primary source). Critique ONLY the concrete proposed "
            "order above — do not invent positions (e.g. shorts) that were not proposed.\n"
            "Choose REDUCE_SIZE over REJECT for a corroborated-but-thin starter. REJECT ONLY "
            "if it breaks a hard limit, or rests on a single uncorroborated source.\n"
            "On the FINAL line, write exactly one of:\n"
            "VERDICT: REJECT\nVERDICT: REDUCE_SIZE\nVERDICT: ACCEPT"
        )
        return await self.router.complete(
            self.name, [Message("system", self.sys(self.role_system)), Message("user", user)]
        )
