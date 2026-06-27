"""Execution adapter interface. Dry mode uses the SimLedger; a future live broker
(IBKR, etc.) implements the same interface, so flipping to live is a config switch,
not a rewrite.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from schemas import PortfolioDecision, SimulatedTrade


class ExecutionAdapter(ABC):
    mode: str = "base"

    @abstractmethod
    async def execute(self, decision: PortfolioDecision) -> SimulatedTrade | None:
        """Apply a decision. Returns the resulting trade, or None for no-trade actions."""
        raise NotImplementedError
