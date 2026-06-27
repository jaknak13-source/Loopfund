"""Human instruction parsing. Messages dropped into the loop are high priority and
override default behavior until cleared/expired. Intent parsing is heuristic and
intentionally conservative — when unsure, it does not change risk behavior.
"""

from __future__ import annotations

import re

NO_TRADE = "no_trade"
DEFENSIVE = "defensive"
AGGRESSIVE = "aggressive"
FOCUS = "focus"  # focus:TICKER
AVOID = "avoid"  # avoid:topic


def parse_intent(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\b(don'?t|do not|no)\s+trade\b|halt trading|stop trading", t):
        return NO_TRADE
    if re.search(r"\b(defensive|less risk|reduce risk|be safe|safer|hedge more)\b", t):
        return DEFENSIVE
    if re.search(r"\b(more risk|aggressive|risk on)\b", t):
        return AGGRESSIVE
    m = re.search(r"\b(?:look at|analyze|check|focus on)\s+([A-Z]{1,5})\b", text)
    if m:
        return f"{FOCUS}:{m.group(1).upper()}"
    m2 = re.search(r"\b(?:avoid|stay away from|no)\s+([a-z]+)\b", t)
    if m2 and m2.group(1) not in ("trade",):
        return f"{AVOID}:{m2.group(1)}"
    return None


def directive_text(intents: list[str]) -> str:
    """Compact human-directive string to inject into agent/decision prompts."""
    if not intents:
        return "None."
    return "; ".join(intents)
