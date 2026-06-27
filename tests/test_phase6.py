"""Phase 6: calibration math (Brier, precision, learned priors)."""

from __future__ import annotations

import math
from datetime import date

from memory import calibration
from schemas import Confidence, PortfolioDecision, TradeAction


def _dec(action, score) -> PortfolioDecision:
    return PortfolioDecision(
        id=f"{action}-{score}", decision_date=date.today(), action=action,
        asset="X", reasoning="r", confidence=Confidence(score=score, low=score - 0.1, high=score + 0.1),
    )


def test_directional_correct() -> None:
    assert calibration.directional_correct(TradeAction.BUY, 0.05) is True
    assert calibration.directional_correct(TradeAction.BUY, -0.05) is False
    assert calibration.directional_correct(TradeAction.SELL, -0.05) is True
    assert calibration.directional_correct(TradeAction.NO_ACTION, 0.05) is None


def test_brier_and_precision() -> None:
    pairs = [
        (_dec(TradeAction.BUY, 0.8), 0.05),   # confident buy, right -> low brier
        (_dec(TradeAction.BUY, 0.7), -0.03),  # confident buy, wrong -> high brier
        (_dec(TradeAction.SELL, 0.6), -0.02), # sell, right
        (_dec(TradeAction.NO_ACTION, 0.5), 0.1),  # ignored
    ]
    m = calibration.evaluate_decisions(pairs)
    assert m["n_scored"] == 3
    assert math.isclose(m["bullish_precision"], 0.5)
    assert math.isclose(m["bearish_precision"], 1.0)
    assert 0.0 <= m["brier_score"] <= 1.0


def test_learned_priors_reward_accuracy() -> None:
    outcomes = [
        ("QuantAgent", "bullish", 0.04),
        ("QuantAgent", "bullish", 0.03),
        ("SentimentAgent", "bullish", -0.05),
        ("SentimentAgent", "bullish", -0.02),
    ]
    hr = calibration.agent_hit_rates(outcomes)
    assert hr["QuantAgent"] == 1.0
    assert hr["SentimentAgent"] == 0.0
    priors = calibration.learned_priors(hr)
    # accurate agent's prior rises vs base, inaccurate falls
    assert priors["QuantAgent"] >= calibration.DEFAULT_PRIORS["QuantAgent"]
    assert priors["SentimentAgent"] < calibration.DEFAULT_PRIORS["SentimentAgent"]
