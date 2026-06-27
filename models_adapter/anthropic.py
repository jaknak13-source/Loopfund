"""Native Anthropic (Claude) backend.

Anthropic's Messages API is NOT OpenAI-compatible: the system prompt is a
top-level field (not a message), `max_tokens` is required, auth uses the
`x-api-key` header plus an `anthropic-version`, and the response text lives in
`content[].text`. This adapter translates the router's generic `Message` list
into that shape.

  ANTHROPIC_API_KEY   required
  ANTHROPIC_BASE_URL  optional, default https://api.anthropic.com

Model ids look like `claude-sonnet-4-6` / `claude-opus-4-8` / `claude-haiku-4-5`.
"""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from core.logging import get_logger
from models_adapter.base import LLMBackend, Message

log = get_logger("anthropic")

DEFAULT_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicBackend(LLMBackend):
    name = "anthropic"

    def __init__(self, base_url: str | None = None, api_key: str = "") -> None:
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key or ""

    @retry(
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
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set — cannot call Claude. Add it to .env "
                "(or paste it in the dashboard Settings tab)."
            )
        # Anthropic takes the system prompt as a top-level field, not a message.
        system_text = "\n\n".join(m.content for m in messages if m.role == "system")
        turns = [
            {"role": ("assistant" if m.role == "assistant" else "user"), "content": m.content}
            for m in messages
            if m.role != "system"
        ]
        if not turns:  # API requires at least one message
            turns = [{"role": "user", "content": system_text or "."}]
        payload: dict = {
            "model": model,
            "messages": turns,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_text:
            payload["system"] = system_text
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self.base_url}/v1/messages", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
        _record_cost(model, data.get("usage"))
        parts = data.get("content") or []
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


def _record_cost(model: str, usage: dict | None) -> None:
    if not usage:
        return
    try:
        from core.cost import cost_meter
        cost_meter().record(
            model,
            int(usage.get("input_tokens", 0)),
            int(usage.get("output_tokens", 0)),
        )
    except Exception:
        pass
