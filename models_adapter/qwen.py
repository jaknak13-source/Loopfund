"""Qwen Cloud backend — Alibaba Cloud Model Studio (DashScope) OpenAI-compatible API.

Calls Qwen models hosted on Alibaba Cloud via the DashScope `/compatible-mode/v1`
`/chat/completions` endpoint. A real API key (`DASHSCOPE_API_KEY`) is required —
unlike the local LM Studio backend, there is no anonymous mode.

Default base URL is the Singapore (international) endpoint. Override with
`QWEN_BASE_URL` for the China / US / Hong Kong regions:
  - Singapore (intl): https://dashscope-intl.aliyuncs.com/compatible-mode/v1
  - US (Virginia):    https://dashscope-us.aliyuncs.com/compatible-mode/v1
  - China (Beijing):  https://dashscope.aliyuncs.com/compatible-mode/v1
  - Hong Kong:        https://cn-hongkong.dashscope.aliyuncs.com/compatible-mode/v1
"""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from core.logging import get_logger
from models_adapter.base import LLMBackend, Message

log = get_logger("qwen")

DEFAULT_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


class QwenBackend(LLMBackend):
    name = "qwen"

    def __init__(self, base_url: str | None = None, api_key: str = "") -> None:
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key or ""

    @retry(
        # Mirror the LM Studio policy: retry genuine transient errors (connection
        # refused, 5xx) but let a timeout fail fast (once) so one slow call can't
        # stall the serialized cycle for minutes.
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
                "DASHSCOPE_API_KEY is not set — cannot call Qwen Cloud. "
                "Add it to .env (get one at Alibaba Cloud Model Studio)."
            )
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
        # Record token usage + USD cost so the dashboard can show exact spend.
        usage = data.get("usage") or {}
        if usage:
            try:
                from core.cost import cost_meter
                cost_meter().record(
                    model,
                    int(usage.get("prompt_tokens", 0)),
                    int(usage.get("completion_tokens", 0)),
                )
            except Exception:  # cost metering must never break inference
                pass
        return data["choices"][0]["message"]["content"]
