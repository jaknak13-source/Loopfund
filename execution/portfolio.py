"""Portfolio state in EUR base currency. Cash + positions (avg cost stored in
EUR). Persisted to a JSON file so the loop survives restarts.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.config import data_dir, settings


@dataclass
class Position:
    asset: str
    qty: float
    avg_cost_eur: float  # per-share cost basis in EUR
    ccy: str = "USD"


@dataclass
class Portfolio:
    cash_eur: float
    positions: dict[str, Position] = field(default_factory=dict)
    realized_pnl_eur: float = 0.0

    def market_value(self, prices_eur: dict[str, float]) -> float:
        pv = 0.0
        for a, pos in self.positions.items():
            px = prices_eur.get(a)
            if px is not None:
                pv += pos.qty * px
        return pv

    def total_value(self, prices_eur: dict[str, float]) -> float:
        return self.cash_eur + self.market_value(prices_eur)

    def weights(self, prices_eur: dict[str, float]) -> dict[str, float]:
        total = self.total_value(prices_eur)
        if total <= 0:
            return {}
        out = {}
        for a, pos in self.positions.items():
            px = prices_eur.get(a)
            if px is not None:
                out[a] = (pos.qty * px) / total
        return out

    def to_dict(self) -> dict:
        return {
            "cash_eur": self.cash_eur,
            "realized_pnl_eur": self.realized_pnl_eur,
            "positions": {a: asdict(p) for a, p in self.positions.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Portfolio":
        positions = {a: Position(**p) for a, p in d.get("positions", {}).items()}
        return cls(cash_eur=d["cash_eur"], positions=positions,
                   realized_pnl_eur=d.get("realized_pnl_eur", 0.0))


class PortfolioStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (data_dir() / "portfolio.json")

    def load(self) -> Portfolio:
        if self.path.exists():
            return Portfolio.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        start = float(settings().get("portfolio", {}).get("starting_cash", 1000.0))
        p = Portfolio(cash_eur=start)
        self.save(p)
        return p

    def save(self, p: Portfolio) -> None:
        self.path.write_text(json.dumps(p.to_dict(), indent=2), encoding="utf-8")
