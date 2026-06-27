"""Rotating watchlist selection. Each cycle the fund focuses on a different slice
of the full universe (so it sweeps large/mid/small caps + ETFs/commodities/FX/crypto
over time instead of staring at the same names), while ALWAYS including current
holdings and a couple of anchors, plus any tickers agents recently proposed.
"""

from __future__ import annotations

from config.universe import dynamic_additions, full_universe

ANCHORS = ["SPY", "QQQ"]  # always priced (benchmark + core)


def sample_watchlist(held: list[str], cycle_index: int, n: int = 28,
                     rotate_window: int = 16) -> list[str]:
    """Build this cycle's focus list.

    - anchors + held positions are always in;
    - a rotating window of the universe advances each cycle (sweeps everything);
    - recent agent-proposed tickers get priority so new ideas get researched fast.
    """
    uni = full_universe()
    if not uni:
        return list(dict.fromkeys(ANCHORS + held))

    # rotating window over the universe
    start = (cycle_index * rotate_window) % len(uni)
    window = [uni[(start + i) % len(uni)] for i in range(rotate_window)]

    # newest agent proposals first (research fresh ideas quickly)
    proposals = list(reversed(dynamic_additions()))[:6]

    picked = list(dict.fromkeys(ANCHORS + held + proposals + window))
    return picked[:max(n, len(ANCHORS) + len(held))]
