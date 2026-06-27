"""Simulated ledger. Real prices, real EUR fees, real FX — only the execution is
simulated. Accounting is exact so dry-mode P&L is trustworthy.

Convention: cost basis is stored per-share in EUR, excluding fees. Fees reduce
cash immediately and are booked into realized P&L, so cash always reconciles:
    total_value == starting_cash + realized_pnl + unrealized_pnl
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from core.logging import get_logger
from execution.fees import compute_fee
from execution.portfolio import Portfolio, Position, PortfolioStore
from schemas import SimulatedTrade

log = get_logger("ledger")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return str(uuid.uuid4())


class SimLedger:
    def __init__(self, portfolio: Portfolio, store: PortfolioStore | None = None,
                 blackboard=None) -> None:
        self.p = portfolio
        self.store = store
        self.bb = blackboard

    def _persist(self, trade: SimulatedTrade) -> None:
        if self.store:
            self.store.save(self.p)
        if self.bb:
            self.bb.write_trade(trade)

    def buy(self, decision_id: str, asset: str, qty: float, price_native: float,
            ccy: str = "USD", fx_rate: float = 1.0) -> SimulatedTrade:
        fill_eur = price_native * fx_rate
        notional_eur = qty * fill_eur
        fee = compute_fee(notional_eur, ccy)
        trade = SimulatedTrade(
            id=_id(), decision_id=decision_id, placed_at=_now(), asset=asset, side="buy",
            qty=qty, ccy=ccy, price_native=price_native, fx_rate=fx_rate,
            fill_price_eur=fill_eur, fees_eur=fee,
        )
        cost = notional_eur + fee
        if cost > self.p.cash_eur + 1e-9:
            trade.status = "rejected"
            log.warning("buy_rejected_insufficient_cash", asset=asset, cost=cost, cash=self.p.cash_eur)
            self._persist(trade)
            return trade

        self.p.cash_eur -= cost
        self.p.realized_pnl_eur -= fee
        pos = self.p.positions.get(asset)
        if pos is None:
            self.p.positions[asset] = Position(asset=asset, qty=qty, avg_cost_eur=fill_eur, ccy=ccy)
        else:
            new_qty = pos.qty + qty
            pos.avg_cost_eur = (pos.qty * pos.avg_cost_eur + qty * fill_eur) / new_qty
            pos.qty = new_qty
        trade.status = "filled"
        log.info("buy_filled", asset=asset, qty=qty, fill_eur=fill_eur, fee=fee, cash=self.p.cash_eur)
        self._persist(trade)
        return trade

    def sell(self, decision_id: str, asset: str, qty: float, price_native: float,
             ccy: str = "USD", fx_rate: float = 1.0) -> SimulatedTrade:
        fill_eur = price_native * fx_rate
        notional_eur = qty * fill_eur
        fee = compute_fee(notional_eur, ccy)
        trade = SimulatedTrade(
            id=_id(), decision_id=decision_id, placed_at=_now(), asset=asset, side="sell",
            qty=qty, ccy=ccy, price_native=price_native, fx_rate=fx_rate,
            fill_price_eur=fill_eur, fees_eur=fee,
        )
        pos = self.p.positions.get(asset)
        if pos is None or pos.qty + 1e-9 < qty:
            trade.status = "rejected"
            log.warning("sell_rejected_no_position", asset=asset, have=getattr(pos, "qty", 0), want=qty)
            self._persist(trade)
            return trade

        realized = qty * (fill_eur - pos.avg_cost_eur) - fee
        self.p.cash_eur += notional_eur - fee
        self.p.realized_pnl_eur += realized
        pos.qty -= qty
        if pos.qty <= 1e-9:
            del self.p.positions[asset]
        trade.realized_pnl_eur = round(realized, 6)
        trade.status = "closed" if (asset not in self.p.positions) else "filled"
        log.info("sell_filled", asset=asset, qty=qty, fill_eur=fill_eur, realized=realized, cash=self.p.cash_eur)
        self._persist(trade)
        return trade

    def mark_to_market(self, prices_eur: dict[str, float]) -> dict:
        unrealized = 0.0
        for a, pos in self.p.positions.items():
            px = prices_eur.get(a)
            if px is not None:
                unrealized += pos.qty * (px - pos.avg_cost_eur)
        return {
            "cash_eur": round(self.p.cash_eur, 2),
            "market_value_eur": round(self.p.market_value(prices_eur), 2),
            "total_value_eur": round(self.p.total_value(prices_eur), 2),
            "realized_pnl_eur": round(self.p.realized_pnl_eur, 2),
            "unrealized_pnl_eur": round(unrealized, 2),
            "n_positions": len(self.p.positions),
        }
