"""Process-wide token + USD cost meter for Qwen Cloud (Model Studio) inference.

Backends call `cost_meter().record(model, prompt_tokens, completion_tokens)` after
each call. The orchestrator snapshots total spend before/after a cycle to report an
exact per-cycle cost, and the dashboard reads the running total from /api/cost.

Prices are USD per 1M tokens on the Model Studio international endpoint (June 2026).
Edit PRICES if your account is on different (e.g. China-region or post-promo) rates.
"""

from __future__ import annotations

import threading

# USD per 1,000,000 tokens: (input, output). Source: Alibaba Cloud Model Studio pricing.
PRICES: dict[str, tuple[float, float]] = {
    "qwen-max": (1.25, 3.75),
    "qwen-plus": (0.40, 1.20),
    "qwen-turbo": (0.05, 0.20),
    "qwen-flash": (0.05, 0.40),
    "qwen-vl-max": (1.60, 4.80),
    # newer ids in use (approximate, mapped to their tier — exact list price varies):
    "qwen3-max": (1.25, 3.75),
    "qwen3.7-plus": (0.40, 1.20),
    "qwen3.5-plus-2026-02-15": (0.40, 1.20),
    "qwen3.5-122b-a10b": (0.40, 1.20),
    "qwen3-vl-30b-a3b-thinking": (1.60, 4.80),
    "qwen3-vl-235b-a22b-thinking": (1.60, 4.80),
}
# Fallback for any model not in the table — use qwen-plus rates (mid-tier).
_DEFAULT_PRICE = (0.40, 1.20)


def price_for(model: str) -> tuple[float, float]:
    return PRICES.get(model, _DEFAULT_PRICE)


def call_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pin, pout = price_for(model)
    return (prompt_tokens * pin + completion_tokens * pout) / 1_000_000.0


class CostMeter:
    """Thread-safe running tally of tokens and USD, broken down by model."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.usd = 0.0
        self.by_model: dict[str, dict] = {}

    def record(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        cost = call_cost_usd(model, prompt_tokens, completion_tokens)
        with self._lock:
            self.calls += 1
            self.prompt_tokens += prompt_tokens
            self.completion_tokens += completion_tokens
            self.usd += cost
            m = self.by_model.setdefault(
                model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "usd": 0.0})
            m["calls"] += 1
            m["prompt_tokens"] += prompt_tokens
            m["completion_tokens"] += completion_tokens
            m["usd"] += cost
        return cost

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "calls": self.calls,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_usd": round(self.usd, 4),
                "by_model": {
                    k: {**v, "usd": round(v["usd"], 4)} for k, v in self.by_model.items()
                },
            }


_METER = CostMeter()


def cost_meter() -> CostMeter:
    return _METER
