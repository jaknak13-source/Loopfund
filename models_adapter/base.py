"""Backend-agnostic LLM interface. Concrete backends: LM Studio, OpenAI, Anthropic."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMBackend(ABC):
    """Minimal completion interface every backend must implement."""

    name: str = "base"

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: float = 180.0,
    ) -> str:
        """Return the assistant's text. Raises on transport/API error."""
        raise NotImplementedError
