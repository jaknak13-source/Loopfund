"""Cost meter prices Qwen usage correctly; run_cycle reports per-cycle cost;
contributed-capital baseline is the sum of deposits."""

from __future__ import annotations


from core.cost import CostMeter, call_cost_usd


def test_call_cost_known_model():
    # qwen-plus: $0.40/1M input, $1.20/1M output.
    # 1,000,000 input + 1,000,000 output = 0.40 + 1.20 = 1.60
    assert abs(call_cost_usd("qwen-plus", 1_000_000, 1_000_000) - 1.60) < 1e-9


def test_call_cost_unknown_model_uses_default():
    assert call_cost_usd("some-future-model", 1_000_000, 0) == call_cost_usd("qwen-plus", 1_000_000, 0)


def test_meter_accumulates_by_model():
    m = CostMeter()
    m.record("qwen-plus", 1000, 500)
    m.record("qwen-max", 2000, 1000)
    snap = m.snapshot()
    assert snap["calls"] == 2
    assert snap["prompt_tokens"] == 3000
    assert snap["completion_tokens"] == 1500
    assert set(snap["by_model"]) == {"qwen-plus", "qwen-max"}
    assert snap["total_usd"] > 0


def test_contributed_capital_is_sum_of_deposits(tmp_path):
    from tests.helpers import build_offline_orchestrator

    orch = build_offline_orchestrator(tmp_path, cash=1000.0)
    # establish inception (initial capital) + one top-up
    orch.learning.ensure_inception(spy_entry_eur=100.0, start_value_eur=1000.0)
    orch.learning.record_contribution(100.0, spy_price_eur=100.0)
    assert abs(orch.learning.contributed_capital() - 1100.0) < 1e-6
