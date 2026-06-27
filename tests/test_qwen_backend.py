"""Qwen Cloud (DashScope) backend: key required, timeout fails fast, success path,
and the router registers it by default."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from models_adapter.base import Message
from models_adapter.qwen import DEFAULT_BASE_URL, QwenBackend


def test_qwen_requires_api_key():
    """No key -> clear RuntimeError, never a silent or cryptic failure."""
    backend = QwenBackend(api_key="")
    with pytest.raises(RuntimeError, match="DASHSCOPE_API_KEY"):
        asyncio.run(backend.complete([Message("user", "hi")], model="qwen-plus"))


def test_qwen_default_endpoint_is_alibaba_cloud():
    """Default region endpoint must be the DashScope OpenAI-compatible URL."""
    backend = QwenBackend(api_key="k")
    assert backend.base_url == DEFAULT_BASE_URL
    assert "dashscope" in backend.base_url and "compatible-mode/v1" in backend.base_url


def test_qwen_does_not_retry_on_timeout():
    """A timeout already burned the budget; retrying 3x stalls the serialized loop."""
    calls = {"n": 0}
    backend = QwenBackend(api_key="k")

    async def boom(*a, **k):
        calls["n"] += 1
        raise httpx.ReadTimeout("busy")

    orig = httpx.AsyncClient.post
    httpx.AsyncClient.post = boom  # type: ignore[assignment]
    try:
        with pytest.raises(httpx.TimeoutException):
            asyncio.run(backend.complete([Message("user", "hi")], model="qwen-plus", timeout=0.01))
    finally:
        httpx.AsyncClient.post = orig  # type: ignore[assignment]
    assert calls["n"] == 1  # NOT 3


def test_qwen_success_path_parses_openai_shape():
    backend = QwenBackend(api_key="k")

    async def ok(*a, **k):
        class _R:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": "BUY NVDA"}}]}

        return _R()

    orig = httpx.AsyncClient.post
    httpx.AsyncClient.post = ok  # type: ignore[assignment]
    try:
        out = asyncio.run(backend.complete([Message("user", "hi")], model="qwen-plus"))
    finally:
        httpx.AsyncClient.post = orig  # type: ignore[assignment]
    assert out == "BUY NVDA"


def test_router_registers_qwen_backend_by_default():
    from models_adapter.router import ModelRouter

    router = ModelRouter()
    assert "qwen" in router.backends
    assert "lmstudio" in router.backends
