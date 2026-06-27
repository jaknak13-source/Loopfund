"""DecisionAgent: the coordinator. Once per cooldown window it aggregates all
reports by evidence weight, gets a RiskAgent rebuttal, asks the model to
synthesize a single decision, then enforces the house rules in code. NO_ACTION is
the default whenever conviction is low or the skeptic rejects.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, date, timezone

from agents import evidence
from agents.base import BaseAgent
from agents.memory_agent import MemoryAgent
from agents.risk import RiskAgent
from agents.util import clamp01, parse_json_block
from core.blackboard import Blackboard
from core.config import risk_limits, settings
from models_adapter.base import Message
from models_adapter.router import ModelRouter
from schemas import Confidence, PortfolioDecision, TradeAction

_SYSTEM = (
    "You are the DecisionAgent, coordinator of an ACTIVELY MANAGED fund — not a "
    "buy-and-hold-the-index strategy. You receive evidence-weighted signals, peer "
    "reports, and a skeptic's rebuttal, and produce ONE decision for this window.\n"
    "Be a real portfolio manager:\n"
    "- INITIATE positions proactively. Idle cash is not 'nothing to do' — your job is "
    "to FIND and BUY the best opportunities the agents surfaced. If you hold excess "
    "cash and any idea has corroborated, appropriately-sized conviction, OPEN a starter "
    "position; do not wait for something to trim before acting.\n"
    "- SIZE BY EDGE: scale the position to the margin of safety and corroboration — a "
    "large, well-corroborated upside (e.g. >30% to fair value) warrants a fuller "
    "position (up to the caps); a thin or uncertain edge gets only a small starter.\n"
    "- TAKE PROFITS on winners and TRIM/EXIT when a thesis weakens, risk rises, or a "
    "better opportunity exists — don't just hold by default.\n"
    "- TIME entries/exits using news, earnings, and metrics. Do NOT add to a position "
    "right before its earnings if the outcome is uncertain.\n"
    "- Hunt asymmetric setups and second-order/cross-market connections (e.g. AI GPU "
    "demand -> memory/components; energy shifts -> nuclear/uranium names), and rotate "
    "into them when evidence supports it.\n"
    "- Still require conviction + >=2 verified sources; NO_ACTION is valid when genuinely "
    "unclear — but do not default to passive holding out of laziness.\n"
    "- FEES COST REAL MONEY. Every buy and every sell pays a fee. Do NOT open a position you "
    "may want to reverse within days, and do NOT trim/sell something you bought very recently — "
    "round-tripping a position in minutes/hours burns fees on BOTH legs and loses money. Trade "
    "with a multi-day-or-longer horizon; exit early only for a real thesis break, stop-loss, or "
    "risk event — not noise.\n"
    "- CONVICTION IN MANY: if SEVERAL names independently clear the bar (each corroborated by "
    ">=2 sources, strong edge), you MAY open more than one this cycle via `additional_buys`. "
    "Only genuinely high-conviction names, each sized prudently within caps.\n"
    "Obey the house rules and risk limits exactly. Never bet on a single unverified claim."
)

_CONTRACT = """Return ONLY JSON:
{"action": "buy|sell|trim|add|hold|hedge|no_action",
 "asset": ticker or null,
 "target_weight": 0-1 or null,
 "reasoning": str,
 "key_assumptions": [str],
 "known_risks": [str],
 "confidence": {"score":0-1,"low":0-1,"high":0-1,"rationale":str},
 "additional_buys": [{"asset": ticker, "target_weight": 0-1, "reasoning": str}]}
Leave "additional_buys" as [] unless 2+ OTHER names each clear the bar (>=2 sources, high
conviction). Never reverse a freshly-opened position (fees cost money)."""

ACTION_CONVICTION_FLOOR = 0.40  # below this -> no_action (corroboration gate still bounds size)
# An opening buy/add with < 2 distinct credible corroborating domains is bounded to a
# SMALL starter (House Rule #2: >=2 sources for a full position; a thin idea may still
# take a small starter). This enforces corroboration symmetrically on the accept path —
# not only inside the REJECT branch — without re-introducing the all-NO_ACTION deadlock.
UNCORROBORATED_STARTER_CAP = 0.06
# Consensus fallback: the weak local model sometimes returns NO_ACTION even when several
# independent agents corroborate a positive idea. To behave like an active PM (and not freeze
# in cash forever), open a SMALL starter on a clearly corroborated consensus long anyway.
CONSENSUS_SIGNAL_MIN = 0.10        # min net per-asset signal to call it a consensus long
CONSENSUS_STARTER_WEIGHT = 0.06    # small, prudent starter (model itself was hesitant)

# The skeptic is instructed to end with a `VERDICT: <token>` line. Prefer that explicit
# trailer (anchored) so prose AFTER the verdict can't flip the call; only if no trailer
# exists at all do we fall back to a loose last-keyword scan.
_VERDICT_TRAILER = re.compile(r"VERDICT:\s*(REJECT|REDUCE[_\- ]?SIZE|ACCEPT)", re.IGNORECASE)
_VERDICT_LOOSE = re.compile(r"\b(REJECT|REDUCE[_\- ]?SIZE|ACCEPT)\b", re.IGNORECASE)


def parse_verdict(rebuttal: str) -> str:
    """Extract the RiskAgent's final verdict. Returns REJECT|REDUCE_SIZE|ACCEPT.

    Anchors to the last `VERDICT: <token>` trailer (the contract) so trailing prose
    can't flip ACCEPT->REJECT. Falls back to the last loose keyword only when no
    trailer is present. Absence -> ACCEPT (no objection is not a veto).
    """
    text = rebuttal or ""
    trailer = _VERDICT_TRAILER.findall(text)
    matches = trailer if trailer else _VERDICT_LOOSE.findall(text)
    if not matches:
        return "ACCEPT"
    tok = matches[-1].upper()
    return "REDUCE_SIZE" if tok.startswith("REDUCE") else tok


class DecisionAgent(BaseAgent):
    name = "DecisionAgent"

    def __init__(self, bb: Blackboard, router: ModelRouter, tools, memory: MemoryAgent,
                 risk_agent: RiskAgent, priors: dict[str, float] | None = None) -> None:
        super().__init__(bb, router, tools)
        self.memory = memory
        self.risk = risk_agent
        self.priors = priors  # learned agent priors (None -> defaults)

    async def run(self, cycle_id: str, portfolio_summary: str = "Empty portfolio (all cash).",
                  human_directive: str = "None.", council_dossier: str = "",
                  holdings: dict[str, float] | None = None) -> PortfolioDecision:
        reports = self.bb.reports_for_cycle(cycle_id)
        agg = evidence.aggregate(reports, self.priors)
        rl = risk_limits()
        mode = settings().get("mode", "dry")

        # cap the peer fan-in to the top-N by evidence weight so the prompt can't overflow
        # the context window (-> HTTP 400) as the self-extending MetaAgent adds agents over a
        # long run. The aggregate signal already incorporates every report.
        ranked_reports = sorted(reports, key=lambda r: evidence.report_weight(r, self.priors), reverse=True)
        peer = "\n".join(
            f"[{r.agent}] {r.stance} conf={r.confidence.score:.2f}: {r.summary[:250]}"
            for r in ranked_reports[:14]
        )
        # surface valuation/edge findings prominently for sizing-by-margin-of-safety
        edge_lines = []
        for r in reports:
            if r.agent in ("ValuationAgent", "FundamentalsAgent", "QuantAgent"):
                for f in r.findings[:4]:
                    edge_lines.append(f"[{r.agent}] {f}")
        edge_txt = "\n".join(edge_lines[:14]) or "no explicit valuation reads this cycle"
        allow_short = bool(rl.get("allow_short", False))
        # verified-source coverage so the model (and skeptic) can SEE the >=2-source count
        corr = agg.get("corroboration", {})
        coverage_txt = (
            "\n".join(f"- {a}: {n} distinct credible source(s)"
                      for a, n in sorted(corr.items(), key=lambda kv: kv[1], reverse=True)[:10])
            or "no verified-source coverage computed this cycle"
        )
        short_line = f"Top short: {agg['top_short']}\n" if allow_short else ""
        evidence_txt = (
            f"Top long: {agg['top_long']}\n{short_line}"
            f"Market signal: {agg['market_signal']:.3f}  Risk brake: {agg['risk_signal']:.3f}\n"
            f"Per-asset net: {dict(list(agg['per_asset'].items())[:10])}\n"
            f"Verified-source coverage:\n{coverage_txt}"
        )
        # recall accumulated deep-dive research relevant to the names in play, so prior
        # work compounds into the decision (the self-improving loop) rather than being write-only.
        top_assets = [a for a, _ in agg.get("ranked", [])[:5]]
        research_q = (" ".join(top_assets) + " thesis valuation catalyst risk"
                      if top_assets else "market thesis valuation risk")
        prior = self.memory.recall(research_q, k=4, kind="research")
        prior_txt = ("\n".join(f"- {h.title}: {h.body[:200]}" for h in prior)
                     or "no prior research recalled (still accumulating)")

        # concrete candidate for the skeptic: the strongest long the evidence actually supports
        cand = agg.get("top_long")
        candidate_line = (f"Proposed: open/add a starter in {cand[0]} (net signal {cand[1]:.3f}, "
                          f"{corr.get(cand[0], 0)} credible sources)" if cand else "Proposed: NO_ACTION")
        candidate_txt = (f"{candidate_line}\nEvidence summary:\n{evidence_txt}\n"
                         f"Portfolio: {portfolio_summary}")

        # skeptic rebuttal (debate step) — critiques the concrete proposed order
        rebuttal = await self.risk.rebut(cycle_id, candidate_txt)

        user = (
            f"House rules:\n{self.house_rules()[:1400]}\n\n"
            f"HUMAN DIRECTIVE (high priority, obey): {human_directive}\n\n"
            f"Risk limits: {rl}\n\n"
            f"Current portfolio: {portfolio_summary}\n\n"
            f"VALUATION & EDGE (use for sizing — bigger corroborated margin of safety -> "
            f"larger position within caps; thin/uncertain edge -> small starter):\n{edge_txt}\n\n"
            f"PRIOR RESEARCH (your accumulated deep dives — inform your view, but re-verify "
            f"against this cycle's data before acting):\n{prior_txt}\n\n"
            f"COUNCIL DELIBERATION (bull vs bear vs synthesis on the top names — weigh this "
            f"multi-perspective debate heavily; a DEVELOP verdict means keep researching, not "
            f"trade-or-drop):\n{council_dossier or 'no deliberation this cycle'}\n\n"
            f"Peer reports:\n{peer}\n\n{evidence_txt}\n\n"
            f"RiskAgent rebuttal:\n{rebuttal}\n\n{_CONTRACT}"
        )
        text = await self.router.complete(self.name, [Message("system", self.sys(_SYSTEM)), Message("user", user)])
        parsed = parse_json_block(text)

        decision = self._finalize(cycle_id, parsed, agg, rebuttal, mode, holdings or {})
        # multi-buy: attach extra high-conviction buys the model surfaced (corroboration- +
        # cap-checked here; the orchestrator fee/risk-checks each before executing).
        if decision.action in (TradeAction.BUY, TradeAction.ADD) and parse_verdict(rebuttal) != "REJECT":
            decision.additional_buys = self._validate_additional_buys(
                parsed, agg, decision.asset, holdings or {})
        self.bb.write_decision(decision)
        self.memory.ingest_decision(decision)
        self.log.info("decision", action=decision.action.value, asset=decision.asset,
                      conf=decision.confidence.score, extra_buys=len(decision.additional_buys))
        return decision

    def _validate_additional_buys(self, parsed, agg, primary_asset, holdings) -> list[dict]:
        """Keep only extra buys that independently clear the bar: corroboration >= 2,
        not the primary, not already at cap. Cap count to decision.max_buys_per_cycle - 1
        and weight to the single-asset cap. Fee/churn/risk checks happen at execution."""
        raw = parsed.get("additional_buys") or []
        if not isinstance(raw, list) or not raw:
            return []
        rl = risk_limits()
        max_w = float(rl.get("max_single_asset_weight", 0.20))
        max_buys = int(settings().get("decision", {}).get("max_buys_per_cycle", 3))
        corr = agg.get("corroboration", {})
        out: list[dict] = []
        seen = {str(primary_asset).upper()} if primary_asset else set()
        for item in raw:
            if len(out) >= max(0, max_buys - 1):
                break
            if not isinstance(item, dict):
                continue
            a = str(item.get("asset", "")).upper().strip()
            if not a or a in seen:
                continue
            if corr.get(a, 0) < 2:  # require >=2 corroborating sources, same bar as primary
                continue
            held = max(0.0, float(holdings.get(a, 0.0))) / 100.0
            if held >= max_w - 1e-3:  # no room
                continue
            tw = clamp01(item.get("target_weight") or UNCORROBORATED_STARTER_CAP)
            tw = min(max(tw, 0.02), max_w)
            seen.add(a)
            out.append({"asset": a, "target_weight": tw,
                        "reasoning": str(item.get("reasoning", ""))[:300]})
        return out

    def _finalize(self, cycle_id, parsed, agg, rebuttal, mode, holdings=None) -> PortfolioDecision:
        holdings = holdings or {}  # {asset: current weight %} so we can ADD vs no-op
        rl = risk_limits()
        max_w = float(rl.get("max_single_asset_weight", 0.20))
        today = _utc_date()

        def no_action(reason: str, score: float = 0.3, block: str = "evidence_insufficient") -> PortfolioDecision:
            return PortfolioDecision(
                id=str(uuid.uuid4()), decision_date=today, created_at=_utcnow(),
                action=TradeAction.NO_ACTION,
                reasoning=reason,
                key_assumptions=[], known_risks=["acting without conviction destroys capital"],
                confidence=Confidence(score=score, low=max(0.0, score - 0.1), high=min(1.0, score + 0.1),
                                      rationale="below conviction floor or skeptic veto"),
                contributing_reports=[], risk_rebuttal=rebuttal, mode=mode, block_reason=block,
            )

        if parsed is None:
            return no_action("Model produced no structured decision; defaulting to NO_ACTION.",
                             block="no_structured_output")

        conf = parsed.get("confidence", {}) or {}
        score = clamp01(conf.get("score", 0.3))
        action_raw = str(parsed.get("action", "no_action")).lower()
        chosen = str(parsed["asset"]).upper() if parsed.get("asset") else None
        corrob = agg.get("corroboration", {}).get(chosen, 0) if chosen else 0

        # skeptic verdict (final token, not a substring anywhere in the text)
        verdict = parse_verdict(rebuttal)
        haircut = "REDUCE_SIZE" in verdict
        if verdict == "REJECT":
            # a REJECT on a well-corroborated (>=2 distinct credible domains) idea becomes a
            # size haircut, not a hard veto — matches STRATEGY.md sizing-by-evidence.
            if chosen and corrob >= 2 and action_raw in ("buy", "add"):
                haircut = True
            else:
                return no_action(
                    f"RiskAgent vetoed (REJECT); {corrob} corroborating credible source(s) for "
                    f"{chosen or 'n/a'} (<2). {str(parsed.get('reasoning',''))[:240]}",
                    score=min(score, 0.4), block="risk_veto")
        if score < ACTION_CONVICTION_FLOOR and action_raw not in ("no_action", "hold", "hedge"):
            return no_action(f"Conviction {score:.2f} below floor {ACTION_CONVICTION_FLOOR}.",
                             score=score, block="below_floor")

        try:
            action = TradeAction(action_raw)
        except ValueError:
            action = TradeAction.NO_ACTION

        # CONSENSUS FALLBACK: the model declined, but if several independent agents corroborate
        # a positive long (and the skeptic didn't hard-reject it), act on the consensus with a
        # small starter rather than freezing in cash. Execution still passes risk caps + cooldown.
        if action == TradeAction.NO_ACTION and verdict != "REJECT":
            corr_map = agg.get("corroboration", {})
            # pick the strongest corroborated positive long that still has ROOM to add (so we
            # don't 'buy' a name already at/over its cap and produce a no-op), and target
            # current weight + a starter step so it actually DEPLOYS.
            for a, net in agg.get("ranked", []):
                if net < CONSENSUS_SIGNAL_MIN or corr_map.get(a, 0) < 2:
                    continue
                held_frac = max(0.0, float(holdings.get(a, 0.0))) / 100.0
                if held_frac >= max_w - 1e-3:
                    continue  # already at the cap — no room, skip to next consensus name
                tw = min(max_w, held_frac + CONSENSUS_STARTER_WEIGHT)
                s = max(score, ACTION_CONVICTION_FLOOR)
                self.log.info("consensus_fallback", asset=a, net=round(float(net), 2),
                              corrob=corr_map[a], held_pct=round(held_frac * 100, 1), target=round(tw, 3))
                verb = "add to" if held_frac > 0.005 else "open a starter in"
                return PortfolioDecision(
                    id=str(uuid.uuid4()), decision_date=today, created_at=_utcnow(),
                    action=(TradeAction.ADD if held_frac > 0.005 else TradeAction.BUY),
                    asset=a, target_weight=tw,
                    reasoning=(f"Consensus action: {corr_map[a]} independent agents corroborate {a} "
                               f"(net signal {float(net):.2f}); the model returned NO_ACTION but the "
                               f"multi-agent evidence supports it — {verb} {a} (held {held_frac*100:.1f}% "
                               f"-> {tw*100:.1f}%) rather than sitting in cash. "
                               + str(parsed.get('reasoning', ''))[:140]),
                    key_assumptions=["multi-agent corroborated consensus long"],
                    known_risks=["model itself was hesitant; sized small/incremental"],
                    confidence=Confidence(score=s, low=max(0.0, s - 0.1), high=min(1.0, s + 0.1),
                                          rationale="multi-agent consensus fallback"),
                    contributing_reports=[r.id for r in self.bb.reports_for_cycle(cycle_id)],
                    risk_rebuttal=rebuttal, mode=mode, block_reason="traded")

        # symmetric corroboration enforcement on the trade path: an uncorroborated
        # opening buy/add is haircut AND bounded to a small starter (not just on REJECT).
        uncorroborated_buy = action in (TradeAction.BUY, TradeAction.ADD) and corrob < 2
        target_w = parsed.get("target_weight")
        if target_w is not None:
            target_w = clamp01(target_w)
            if haircut or uncorroborated_buy:
                target_w *= 0.5
            target_w = min(target_w, max_w)  # enforce concentration cap
            if uncorroborated_buy:
                target_w = min(target_w, UNCORROBORATED_STARTER_CAP)

        low = min(clamp01(conf.get("low", score - 0.12)), score)
        high = max(clamp01(conf.get("high", score + 0.12)), score)
        block = "model_no_action" if action == TradeAction.NO_ACTION else "traded"
        return PortfolioDecision(
            id=str(uuid.uuid4()), decision_date=today, created_at=_utcnow(), action=action,
            asset=(str(parsed["asset"]).upper() if parsed.get("asset") else None),
            target_weight=target_w,
            reasoning=str(parsed.get("reasoning", ""))[:2000],
            key_assumptions=[str(x) for x in parsed.get("key_assumptions", [])][:10],
            known_risks=[str(x) for x in parsed.get("known_risks", [])][:10],
            confidence=Confidence(score=score, low=low, high=high,
                                  rationale=str(conf.get("rationale", ""))[:300]),
            contributing_reports=[r.id for r in self.bb.reports_for_cycle(cycle_id)],
            risk_rebuttal=rebuttal, mode=mode, block_reason=block,
        )


def _utc_date() -> date:
    return datetime.now(timezone.utc).date()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
