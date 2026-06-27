"""Deterministic mock backend for tests and offline loop development.

`canned` may be a fixed string or a callable that inspects the messages and
returns a response — useful when one backend must serve several agent roles in a
single cycle (JSON analysts + plain-text rebuttals).
"""

from __future__ import annotations

from typing import Callable

from models_adapter.base import LLMBackend, Message

Responder = Callable[[list[Message]], str]


class MockBackend(LLMBackend):
    name = "mock"

    def __init__(self, canned: str | Responder = "OK") -> None:
        self.canned = canned
        self.calls: list[list[Message]] = []

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: float = 180.0,
    ) -> str:
        self.calls.append(messages)
        if callable(self.canned):
            return self.canned(messages)
        return self.canned
