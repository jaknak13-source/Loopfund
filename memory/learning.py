"""Self-learning state. Persists across runs. Three things it learns:

1. Agent reliability  — hit rate of each agent's stance vs realized asset moves,
   fed back into evidence weighting (learned priors).
2. Source trust       — hit rate of each news source/domain, surfaced to the
   ResearchAgent so it learns which news to trust and which to ignore.
3. Benchmark          — strategy equity vs SP500 (SPY) buy-and-hold from inception.

The orchestrator records one observation per (agent, asset, stance) each cycle
with the asset's entry price. After `horizon_days`, the observation matures: the
forward return is computed and the tallies update. This is how the system finds
out — from outcomes — what to trust, without a human labelling anything.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from agents.evidence import DEFAULT_PRIORS
from core.config import data_dir, settings
from memory import calibration


def _now() -> datetime:
    return datetime.now(timezone.utc)


def domain_of(source: str) -> str:
    if not source:
        return "unknown"
    if "://" in source:
        net = urlparse(source).netloc.lower()
        return net[4:] if net.startswith("www.") else net
    return source.lower()[:60]


class LearningStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (data_dir() / "learning.json")
        self.state = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            state = json.loads(self.path.read_text(encoding="utf-8"))
            self._migrate_contributions(state)
            return state
        return {
            "inception": None,            # {date, start_value_eur, spy_entry_eur}
            "weekly": {"last_topup_iso": None},
            "contributions": [],          # ledger of external capital: [{amount, spy_price}]
            "pending": [],                # observations awaiting maturity
            "agent_tally": {},            # agent -> {n, hits}
            "source_tally": {},           # domain -> {n, hits}
            "metrics": {},
        }

    @staticmethod
    def _migrate_contributions(state: dict) -> None:
        """One-time backfill for pre-ledger files: a top-up that already hit cash but was
        never recorded would otherwise count as strategy return (the ~10% inflation bug)."""
        inc = state.get("inception")
        if not inc or "contributions" in state:
            return
        state["contributions"] = []
        # drop the buggy intermediate running fields (recomputed from the ledger now)
        state.pop("invested_capital_eur", None)
        state.pop("spy_units", None)
        last = (state.get("weekly") or {}).get("last_topup_iso")
        if not last:
            return
        try:
            amt = float(settings().get("portfolio", {}).get("weekly_topup", 0.0))
        except Exception:
            amt = 0.0
        if amt <= 0:
            return
        # A legacy file only records the LAST top-up time, not a full history, so we
        # can't know how many fired. `last_topup_iso` proves exactly one thing: at
        # least one top-up already hit cash. Backfill that one (deterministic, and it
        # keeps injected cash out of strategy return). The new ledger tracks the rest.
        spy = inc.get("spy_entry_eur")
        state["contributions"] = [{"amount": amt, "spy_price": spy}]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    # --- inception / benchmark ---
    def ensure_inception(self, spy_entry_eur: float | None, start_value_eur: float) -> None:
        if self.state["inception"] is None and spy_entry_eur:
            self.state["inception"] = {
                "date": _now().isoformat(),
                "start_value_eur": start_value_eur,
                "spy_entry_eur": spy_entry_eur,
            }
            self.state.setdefault("contributions", [])

    def _contrib_base(self) -> tuple[float, float]:
        """Invested capital + notional SPY units, derived from the contributions LEDGER
        (the durable source of truth). Each top-up grows BOTH the strategy base and the
        SPY side, so injected cash is never counted as a return."""
        inc = self.state.get("inception")
        if not inc:
            return 0.0, 0.0
        start = float(inc["start_value_eur"])
        spy_entry = inc.get("spy_entry_eur")
        cap = start
        units = (start / spy_entry) if spy_entry else 0.0
        for c in self.state.get("contributions", []):
            amt = float(c.get("amount", 0.0))
            cap += amt
            sp = c.get("spy_price")
            if sp:
                units += amt / float(sp)
        return cap, units

    def record_contribution(self, amount_eur: float, spy_price_eur: float | None) -> None:
        """Append external capital (e.g. weekly top-up) to the ledger."""
        if amount_eur <= 0 or self.state.get("inception") is None:
            return
        self.state.setdefault("contributions", []).append(
            {"amount": amount_eur, "spy_price": spy_price_eur})

    def contributed_capital(self) -> float:
        """Total external capital put in (initial + every top-up) = the 'cash-only'
        baseline: what you'd have if you never invested, ignoring interest."""
        return self._contrib_base()[0]

    def benchmark(self, spy_now_eur: float | None, portfolio_value_eur: float) -> dict:
        inc = self.state["inception"]
        if not inc or not spy_now_eur:
            return {"available": False}
        cap, units = self._contrib_base()
        if cap <= 0:
            return {"available": False}
        strat = portfolio_value_eur / cap - 1.0
        spy_value = units * spy_now_eur
        spy = spy_value / cap - 1.0
        return {
            "available": True,
            "since": inc["date"],
            "invested_capital_eur": cap,
            "strategy_return": strat,
            "sp500_return": spy,
            "excess_return": strat - spy,
            "beating_sp500": strat > spy,
        }

    # --- weekly top-up ---
    def maybe_weekly_topup(self, amount: float) -> float:
        last = self.state["weekly"]["last_topup_iso"]
        if amount <= 0:
            return 0.0
        if last and _now() < datetime.fromisoformat(last) + timedelta(days=7):
            return 0.0
        self.state["weekly"]["last_topup_iso"] = _now().isoformat()
        return amount

    # --- observations ---
    def add_observation(self, agent: str, asset: str, stance: str,
                        sources: list[str], entry_price_eur: float) -> None:
        if stance not in ("bullish", "bearish"):
            return
        self.state["pending"].append({
            "ts": _now().isoformat(), "agent": agent, "asset": asset, "stance": stance,
            "sources": [domain_of(s) for s in sources][:10], "entry": entry_price_eur,
        })

    def matured_assets(self, horizon_days: int) -> set[str]:
        cutoff = _now() - timedelta(days=horizon_days)
        return {o["asset"] for o in self.state["pending"]
                if datetime.fromisoformat(o["ts"]) <= cutoff}

    def resolve(self, prices_eur: dict[str, float], horizon_days: int) -> dict:
        """Resolve matured observations using current prices. Updates tallies + priors."""
        cutoff = _now() - timedelta(days=horizon_days)
        still_pending, resolved = [], []
        for o in self.state["pending"]:
            mature = datetime.fromisoformat(o["ts"]) <= cutoff
            px = prices_eur.get(o["asset"])
            if not mature or px is None or not o.get("entry"):
                still_pending.append(o)
                continue
            ret = px / o["entry"] - 1.0
            hit = (ret > 0) if o["stance"] == "bullish" else (ret < 0)
            self._bump(self.state["agent_tally"], o["agent"], hit)
            for dom in o["sources"]:
                self._bump(self.state["source_tally"], dom, hit)
            resolved.append({**o, "fwd_return": ret, "hit": hit})
        self.state["pending"] = still_pending
        return {"resolved": len(resolved), "details": resolved}

    @staticmethod
    def _bump(tally: dict, key: str, hit: bool) -> None:
        t = tally.setdefault(key, {"n": 0, "hits": 0})
        t["n"] += 1
        t["hits"] += int(hit)

    # --- learned outputs ---
    def priors(self, min_samples: int = 5) -> dict[str, float]:
        hr = {a: t["hits"] / t["n"] for a, t in self.state["agent_tally"].items()
              if t["n"] >= min_samples}
        return calibration.learned_priors(hr, DEFAULT_PRIORS)

    def source_guidance_text(self, min_samples: int = 4, top_k: int = 6) -> str:
        rated = [(d, t["hits"] / t["n"], t["n"]) for d, t in self.state["source_tally"].items()
                 if t["n"] >= min_samples]
        if not rated:
            return "No source track record yet — treat all sources skeptically, require >=2."
        rated.sort(key=lambda x: x[1], reverse=True)
        trust = [d for d, hr, _ in rated if hr >= 0.55][:top_k]
        distrust = [d for d, hr, _ in rated if hr <= 0.45][:top_k]
        parts = []
        if trust:
            parts.append("Sources with a good track record: " + ", ".join(trust))
        if distrust:
            parts.append("Sources that have been unreliable (discount these): " + ", ".join(distrust))
        return ". ".join(parts) if parts else "Source track record still mixed — stay skeptical."

    def metrics_snapshot(self) -> dict:
        agents = {a: {"n": t["n"], "hit_rate": (t["hits"] / t["n"] if t["n"] else None)}
                  for a, t in self.state["agent_tally"].items()}
        sources = sorted(
            ({"domain": d, "n": t["n"], "hit_rate": (t["hits"] / t["n"] if t["n"] else None)}
             for d, t in self.state["source_tally"].items()),
            key=lambda x: (x["n"], x["hit_rate"] or 0), reverse=True,
        )[:25]
        return {
            "agents": agents,
            "top_sources": sources,
            "pending_observations": len(self.state["pending"]),
            "learned_priors": self.priors(),
        }
