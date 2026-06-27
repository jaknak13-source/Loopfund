"""SEC XBRL financials parsing + tool registration."""

from __future__ import annotations

from core.blackboard import Blackboard
from tools import filings
from tools.data_tools import build_data_registry


def test_latest_annual_picks_newest_10k() -> None:
    facts = {
        "Revenues": {"units": {"USD": [
            {"form": "10-K", "fp": "FY", "end": "2022-12-31", "val": 80.0},
            {"form": "10-K", "fp": "FY", "end": "2023-12-31", "val": 100.0},
            {"form": "10-Q", "fp": "Q1", "end": "2023-03-31", "val": 25.0},
        ]}}
    }
    latest, series = filings._latest_annual(facts, ["Revenues"])
    assert latest == 100.0
    assert series[:2] == [100.0, 80.0]   # newest first, annuals only


def test_latest_annual_missing_tag() -> None:
    latest, series = filings._latest_annual({}, ["Revenues", "SalesRevenueNet"])
    assert latest is None and series == []


def test_sec_financials_registered(tmp_path) -> None:
    reg = build_data_registry(Blackboard(path=tmp_path / "t.db"))
    assert "sec_financials" in reg.available()
