"""Universal OpenAI-compatible backend.

One backend class that talks to ANY server exposing the OpenAI
`/chat/completions` shape. The router registers several named presets built on
this class so users can pick an endpoint by name in `config/models.yaml`:

  local       -> http://localhost:1234/v1      (LM Studio, default; no key)
  ollama      -> http://localhost:11434/v1     (Ollama OpenAI-compat; no key)
  vllm        -> http://localhost:8000/v1      (vLLM / LocalAI; no key)
  openai      -> https://api.openai.com/v1     (OPENAI_API_KEY)
  openrouter  -> https://openrouter.ai/api/v1  (OPENROUTER_API_KEY)
  groq        -> https://api.groq.com/openai/v1(GROQ_API_KEY)
  together    -> https://api.together.xyz/v1   (TOGETHER_API_KEY)
  deepseek    -> https://api.deepseek.com/v1   (DEEPSEEK_API_KEY)
  mistral     -> https://api.mistral.ai/v1     (MISTRAL_API_KEY)
  xai         -> https://api.x.ai/v1           (XAI_API_KEY)

Every preset's base URL and key can be overridden via the matching env var, so
any other OpenAI-compatible host works too — just point one of these at it.
"""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from core.logging import get_logger
from models_adapter.base import LLMBackend, Message

log = get_logger("openai_compat")


class OpenAICompatBackend(LLMBackend):
    """Generic backend for any OpenAI-compatible `/chat/completions` endpoint."""

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        *,
        name: str = "openai",
        requires_key: bool = False,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.requires_key = requires_key
        self.extra_headers = extra_headers or {}

    @retry(
        # Retry genuine transient errors (connection refused, 5xx) but let a
        # timeout fail fast so one slow call can't stall the serialized loop.
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
        if self.requires_key and not self.api_key:
            raise RuntimeError(
                f"{self.name}: API key is not set. Add the matching key to .env "
                f"(or paste one in the dashboard Settings tab), or switch "
                f"config/models.yaml to a local backend."
            )
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
        _record_cost(model, data.get("usage"))
        return data["choices"][0]["message"]["content"]


def _record_cost(model: str, usage: dict | None) -> None:
    """Record token usage + USD cost when the endpoint reports it. Never raises."""
    if not usage:
        return
    try:
        from core.cost import cost_meter
        cost_meter().record(
            model,
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
        )
    except Exception:  # cost metering must never break inference
        pass
