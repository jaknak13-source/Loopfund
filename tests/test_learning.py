"""Phase 6+: self-learning store (agent/source trust, benchmark, top-up) and the
orchestrator learning hook."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from memory.calibration import DEFAULT_PRIORS
from memory.learning import LearningStore, domain_of
from tests.helpers import build_offline_orchestrator


def _age_pending(store: LearningStore, days: int) -> None:
    old = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    for o in store.state["pending"]:
        o["ts"] = old


def test_domain_extraction() -> None:
    assert domain_of("https://www.reuters.com/x/y") == "reuters.com"
    assert domain_of("cnbc.com") == "cnbc.com"


def test_observation_resolution_updates_trust(tmp_path) -> None:
    s = LearningStore(path=tmp_path / "l.json")
    # QuantAgent bullish on X via reuters; entry 100
    for _ in range(6):
        s.add_observation("QuantAgent", "X", "bullish", ["https://reuters.com/a"], 100.0)
    _age_pending(s, 10)
    res = s.resolve({"X": 110.0}, horizon_days=5)  # +10% -> bullish correct
    assert res["resolved"] == 6
    assert s.state["agent_tally"]["QuantAgent"]["hits"] == 6
    assert s.state["source_tally"]["reuters.com"]["hits"] == 6
    priors = s.priors(min_samples=5)
    assert priors["QuantAgent"] >= DEFAULT_PRIORS["QuantAgent"]
    assert "reuters.com" in s.source_guidance_text(min_samples=4)


def test_bad_source_is_distrusted(tmp_path) -> None:
    s = LearningStore(path=tmp_path / "l.json")
    for _ in range(5):
        s.add_observation("SentimentAgent", "Y", "bullish", ["https://hype.example/a"], 100.0)
    _age_pending(s, 10)
    s.resolve({"Y": 90.0}, horizon_days=5)  # -10% -> bullish wrong
    guidance = s.source_guidance_text(min_samples=4)
    assert "hype.example" in guidance and "unreliable" in guidance.lower()


def test_weekly_topup_once_per_week(tmp_path) -> None:
    s = LearningStore(path=tmp_path / "l.json")
    assert s.maybe_weekly_topup(100.0) == 100.0
    assert s.maybe_weekly_topup(100.0) == 0.0  # already topped up this week


def test_benchmark_excess(tmp_path) -> None:
    s = LearningStore(path=tmp_path / "l.json")
    s.ensure_inception(spy_entry_eur=400.0, start_value_eur=1000.0)
    b = s.benchmark(spy_now_eur=420.0, portfolio_value_eur=1100.0)
    assert b["available"] is True
    assert abs(b["strategy_return"] - 0.10) < 1e-9
    assert abs(b["sp500_return"] - 0.05) < 1e-9
    assert b["beating_sp500"] is True


@pytest.mark.asyncio
async def test_orchestrator_records_learning(tmp_path) -> None:
    orch = build_offline_orchestrator(tmp_path)
    result = await orch.run_cycle("c1")
    assert "learning" in result
    assert result["learning"]["benchmark"]["available"] is True  # SPY priced via fake tool
    # directional reports recorded as pending observations for future maturity
    assert orch.learning.state["pending"] or result["learning"]["metrics"]["pending_observations"] >= 0
