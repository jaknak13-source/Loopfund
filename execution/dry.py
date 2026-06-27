"""Dry-mode execution: translate a PortfolioDecision into a simulated trade using
live prices and FX. Sizes to the decision's target weight, enforces risk limits,
and books the fill in the SimLedger.
"""

from __future__ import annotations

from core.config import settings
from core.logging import get_logger
from execution.base import ExecutionAdapter
from execution.fees import compute_fee
from execution.portfolio import Portfolio
from execution.risk_guard import validate_buy
from execution.sim_ledger import SimLedger
from schemas import PortfolioDecision, SimulatedTrade, TradeAction
from tools.registry import ToolRegistry

_BUY_ACTIONS = {TradeAction.BUY, TradeAction.ADD}
_SELL_ACTIONS = {TradeAction.SELL, TradeAction.TRIM}


class DryExecution(ExecutionAdapter):
    mode = "dry"

    def __init__(self, tools: ToolRegistry, ledger: SimLedger) -> None:
        self.tools = tools
        self.ledger = ledger

    @property
    def portfolio(self) -> Portfolio:
        return self.ledger.p

    async def _quote(self, asset: str) -> tuple[float, float, str, float] | None:
        """Return (price_eur, price_native, ccy, fx_rate) or None if unavailable.

        Pricing is read-only plumbing (also hit by frequent dashboard polls), so it
        is NOT logged as an agent ToolCall — logging every poll bloated the DB
        (~16k rows/12h). _log=False skips the audit write but still routes via tools."""
        px, _ = await self.tools.call("DryExecution", "price", ticker=asset, _log=False)
        if px.get("price") is None:
            return None
        ccy = px.get("ccy", "USD")
        native = float(px["price"])
        fxr, _ = await self.tools.call("DryExecution", "fx_rate", base=ccy, quote="EUR", _log=False)
        rate = fxr.get("rate")
        if rate is None:
            return None
        return native * rate, native, ccy, float(rate)

    async def _prices_eur(self, assets: set[str]) -> dict[str, float]:
        out: dict[str, float] = {}
        for a in assets:
            q = await self._quote(a)
            if q is not None:
                out[a] = q[0]
        return out

    async def execute(self, decision: PortfolioDecision) -> SimulatedTrade | None:
        if decision.action in (TradeAction.NO_ACTION, TradeAction.HOLD, TradeAction.HEDGE):
            return None
        asset = decision.asset
        if not asset:
            return None

        quote = await self._quote(asset)
        if quote is None:
            return None
        price_eur, price_native, ccy, fx_rate = quote

        # value the whole book (holdings + target asset) for weight sizing
        assets = set(self.portfolio.positions) | {asset}
        prices_eur = await self._prices_eur(assets)
        prices_eur[asset] = price_eur
        total = self.portfolio.total_value(prices_eur)

        if decision.action in _BUY_ACTIONS:
            target_w = decision.target_weight if decision.target_weight is not None else 0.05
            target_val = target_w * total
            cur_val = 0.0
            pos = self.portfolio.positions.get(asset)
            if pos:
                cur_val = pos.qty * price_eur
            eur_amount = max(0.0, target_val - cur_val)
            fee = compute_fee(eur_amount, ccy)
            # The fee drains total value, so naive sizing to target_val can realize a
            # weight just over the cap. Clamp so the post-fee realized weight stays <= cap.
            from execution.risk_guard import cap_for
            max_w = cap_for(asset)
            amount_cap = max_w * (total - fee) - cur_val
            eur_amount = min(eur_amount, max(0.0, amount_cap))
            if eur_amount < 1.0:  # nothing meaningful to add
                return None
            fee = compute_fee(eur_amount, ccy)  # final fee on the (possibly clamped) amount
            # fee-efficiency guard: skip a trade so small that the fee eats too much of it
            # (kills fee-bleeding micro-rebalances — the main P&L drag). execution.max_fee_pct.
            max_fee_pct = float(settings().get("execution", {}).get("max_fee_pct", 0.0))
            if max_fee_pct > 0 and fee / eur_amount > max_fee_pct:
                get_logger("dry").info("trade_skipped_fee_inefficient", asset=asset,
                                       eur=round(eur_amount, 2), fee=fee,
                                       fee_pct=round(fee / eur_amount, 4), max=max_fee_pct)
                return None
            ok, reason = validate_buy(self.portfolio, asset, eur_amount, fee, prices_eur)
            if not ok:
                get_logger("dry").warning("order_blocked", asset=asset, reason=reason)
                return None
            qty = eur_amount / price_eur
            return self.ledger.buy(decision.id, asset, qty, price_native, ccy, fx_rate)

        if decision.action in _SELL_ACTIONS:
            pos = self.portfolio.positions.get(asset)
            if not pos:
                return None
            if decision.action == TradeAction.SELL or decision.target_weight is None:
                qty = pos.qty  # full exit
            else:
                target_val = decision.target_weight * total
                cur_val = pos.qty * price_eur
                sell_val = max(0.0, cur_val - target_val)
                qty = min(pos.qty, sell_val / price_eur)
            if qty <= 1e-9:
                return None
            return self.ledger.sell(decision.id, asset, qty, price_native, ccy, fx_rate)

        return None
