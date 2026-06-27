"""Helpers for turning LLM text into structured data robustly."""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def parse_json_block(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object from an LLM response. Tolerates code fences,
    surrounding prose, and reasoning-model <think>...</think> blocks (stripped so
    braces inside the reasoning don't corrupt extraction). Returns None if nothing
    parseable is found.
    """
    if not text:
        return None
    text = _THINK.sub(" ", text)  # drop reasoning blocks before extracting JSON
    candidates: list[str] = []
    m = _FENCE.search(text)
    if m:
        candidates.append(m.group(1))
    # greedy first { ... last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start : end + 1])
    candidates.append(text)
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))
