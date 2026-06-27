"""Dashboard API-key input sets the live backend (without clobbering the real .env in
tests), and code execution fails CLOSED when no OS sandbox is available."""

from __future__ import annotations

import asyncio
import os

from fastapi.testclient import TestClient

import dashboard.api.server as server
from dashboard.api.server import create_app
from tests.helpers import build_offline_orchestrator


def test_set_api_key_updates_backend_without_writing_real_env(tmp_path, monkeypatch):
    # never touch the real .env: redirect persistence to an in-memory env-only stub
    written = {}

    def fake_persist(k, v):
        os.environ[k] = v
        written[k] = v

    monkeypatch.setattr(server, "persist_env", fake_persist)
    orch = build_offline_orchestrator(tmp_path)
    # ensure a keyed (cloud) backend exists to update
    from models_adapter.qwen import QwenBackend
    orch.router.backends["qwen"] = QwenBackend(api_key="")
    client = TestClient(create_app(orch))

    # the API-key endpoint is backend-agnostic; name the cloud backend explicitly
    r = client.post("/api/apikey", json={"key": "sk-test-ABCDEFGHIJKLMNOP", "backend": "qwen"})
    assert r.status_code == 200
    body = r.json()
    assert body["set"] is True
    assert body["backend"] == "qwen"
    assert body["masked"].startswith("sk-") and "…" in body["masked"]   # masked, not echoed raw
    assert "ABCDEFGH" not in body["masked"]                              # middle hidden
    assert orch.router.backends["qwen"].api_key == "sk-test-ABCDEFGHIJKLMNOP"  # live backend updated
    assert written["DASHSCOPE_API_KEY"] == "sk-test-ABCDEFGHIJKLMNOP"


def test_empty_api_key_rejected(tmp_path):
    orch = build_offline_orchestrator(tmp_path)
    client = TestClient(create_app(orch))
    assert client.post("/api/apikey", json={"key": "   "}).status_code == 400


def test_code_execution_fails_closed_without_sandbox(monkeypatch):
    """On a host with no OS sandbox (e.g. Linux/ECS), model-authored code must be
    REFUSED, not run with only a static guard — unless explicitly overridden."""
    from core import sandbox as sbx
    from tools import code_runner

    monkeypatch.setattr(code_runner, "code_execution_allowed", lambda: True)
    monkeypatch.setattr(sbx, "wrap_cmd", lambda *a, **k: None)  # simulate "no sandbox-exec"
    monkeypatch.delenv("LOOPFUND_ALLOW_UNSANDBOXED", raising=False)

    out = asyncio.run(code_runner.run_python("print('hi')", "t"))
    assert out["ok"] is False
    assert out.get("blocked") is True
    assert "sandbox" in out["error"].lower()
