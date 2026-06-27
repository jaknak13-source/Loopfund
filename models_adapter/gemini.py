"""Native Google Gemini backend.

Gemini's generateContent API is NOT OpenAI-compatible: messages are `contents`
with `parts`, the assistant role is called `model`, the system prompt goes in
`systemInstruction`, sampling params live under `generationConfig`, and the key
is passed as an `x-goog-api-key` header. This adapter does that translation.

  GEMINI_API_KEY (or GOOGLE_API_KEY)   required
  GEMINI_BASE_URL                       optional, default
                                        https://generativelanguage.googleapis.com

Model ids look like `gemini-2.5-flash` / `gemini-2.5-pro`.

(Note: Gemini also ships an OpenAI-compatible endpoint at
`.../v1beta/openai/` — you can alternatively use the `openai` preset pointed
there. This native adapter avoids that extra hop.)
"""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from core.logging import get_logger
from models_adapter.base import LLMBackend, Message

log = get_logger("gemini")

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"


class GeminiBackend(LLMBackend):
    name = "gemini"

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
                "GEMINI_API_KEY (or GOOGLE_API_KEY) is not set — cannot call Gemini. "
                "Add it to .env (or paste it in the dashboard Settings tab)."
            )
        system_text = "\n\n".join(m.content for m in messages if m.role == "system")
        contents = [
            {
                "role": ("model" if m.role == "assistant" else "user"),
                "parts": [{"text": m.content}],
            }
            for m in messages
            if m.role != "system"
        ]
        if not contents:
            contents = [{"role": "user", "parts": [{"text": system_text or "."}]}]
        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        headers = {"content-type": "application/json", "x-goog-api-key": self.api_key}
        url = f"{self.base_url}/v1beta/models/{model}:generateContent"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        _record_cost(model, data.get("usageMetadata"))
        candidates = data.get("candidates") or []
        if not candidates:
            return ""
        parts = (candidates[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts)


def _record_cost(model: str, usage: dict | None) -> None:
    if not usage:
        return
    try:
        from core.cost import cost_meter
        cost_meter().record(
            model,
            int(usage.get("promptTokenCount", 0)),
            int(usage.get("candidatesTokenCount", 0)),
        )
    except Exception:
        pass
