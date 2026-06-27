"""LM Studio backend via its OpenAI-compatible /chat/completions endpoint.

Retries transient failures with exponential backoff. LM Studio needs no real
API key; any non-empty string works.
"""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from core.logging import get_logger
from models_adapter.base import LLMBackend, Message

log = get_logger("lmstudio")


class LMStudioBackend(LLMBackend):
    name = "lmstudio"

    def __init__(self, base_url: str, api_key: str = "lm-studio") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "lm-studio"

    @retry(
        # A timeout already burned the full request budget — retrying it 3x just
        # stalls the single-slot serialized loop for minutes. Retry genuine transient
        # errors (connection refused, 5xx) but let timeouts fail fast (once).
        retry=retry_if_not_exception_type(httpx.TimeoutException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        reraise=True,
    )
    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout: float = 180.0,
    ) -> str:
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]
