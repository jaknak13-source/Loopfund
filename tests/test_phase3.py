"""Phase 3: quant math correctness + QuantAgent end-to-end (synthetic data)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from agents.quant import QuantAgent
from core.blackboard import Blackboard
from models_adapter.mock import MockBackend
from models_adapter.router import ModelRouter
from quant import artifacts, backtest, factors, montecarlo, regime, sizing
from tools.registry import ToolRegistry


def test_monte_carlo_deterministic() -> None:
    a = montecarlo.simulate_gbm(100, 0.0005, 0.02, horizon_days=21, n_paths=5000, seed=1)
    b = montecarlo.simulate_gbm(100, 0.0005, 0.02, horizon_days=21, n_paths=5000, seed=1)
    assert a["expected_price"] == b["expected_price"]
    assert 0.0 <= a["prob_loss"] <= 1.0


def test_kelly_known_value() -> None:
    # p=0.6, b=2 -> f* = 0.6 - 0.4/2 = 0.4
    assert math.isclose(sizing.kelly_fraction(0.6, 2.0), 0.4, rel_tol=1e-9)
    # never exceeds half-Kelly cap (0.5) * asset cap (0.20)
    out = sizing.sized_weight(0.6, 2.0)
    assert out["recommended_weight"] <= 0.20


def test_momentum_positive_on_uptrend() -> None:
    closes = list(np.linspace(100, 200, 300))
    m = factors.momentum(closes)
    assert m is not None and m > 0


def test_backtest_uptrend_full_exposure_profitable() -> None:
    closes = list(np.linspace(100, 130, 120))
    sig = [1.0] * 120
    res = backtest.backtest_signal(closes, sig, cost_bps=0.0)
    assert res["total_return"] > 0
    assert res["max_drawdown"] <= 0.0


def test_regime_risk_on_for_steady_uptrend() -> None:
    rng = np.random.default_rng(0)
    closes = [100.0]
    for _ in range(200):
        closes.append(closes[-1] * (1 + 0.0006 + rng.normal(0, 0.004)))
    reg = regime.detect_regime(closes)
    assert reg["regime"] in ("risk_on", "neutral")  # steady low-vol uptrend


@pytest.mark.asyncio
async def test_quant_agent_end_to_end(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(artifacts, "ARTIFACT_DIR", tmp_path / "artifacts")
    # also patch the reference imported into the agent module
    import agents.quant as q
    monkeypatch.setattr(q, "save_artifact", lambda name, payload: artifacts.save_artifact(name, payload))

    rng = np.random.default_rng(7)

    def _series() -> list[dict]:
        closes = [100.0]
        for _ in range(260):
            closes.append(closes[-1] * (1 + 0.0005 + rng.normal(0, 0.012)))
        return [{"close": c} for c in closes]

    bb = Blackboard(path=tmp_path / "t.db")
    reg_tools = ToolRegistry(bb)

    async def _history(**kwargs):
        return {"ticker": kwargs.get("ticker"), "bars": _series(), "stale": False}

    reg_tools.register("history", _history)
    router = ModelRouter(backends={"lmstudio": MockBackend("OK")}, max_concurrent=1)

    agent = QuantAgent(bb, router, reg_tools, watchlist=["NVDA", "AAPL"], index_symbol="SPY")
    report = await agent.run("c1")

    assert report.agent == "QuantAgent"
    assert set(report.assets) == {"NVDA", "AAPL"}
    assert any("Regime:" in f for f in report.findings)
    assert (tmp_path / "artifacts").exists()
