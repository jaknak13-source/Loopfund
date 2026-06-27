"""Live smoke test: prove the fund can reach Qwen models on Alibaba Cloud.

Run after putting DASHSCOPE_API_KEY in .env:
    .venv/bin/python scripts/smoke_qwen.py

Calls qwen-turbo (cheap) and qwen-plus through the same ModelRouter the agents use.
Prints the model's reply and the resolved backend/endpoint. Non-zero exit on failure.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # project root on path

from core.config import env
from models_adapter.base import Message
from models_adapter.router import ModelRouter


async def main() -> int:
    key = env("DASHSCOPE_API_KEY", "") or ""
    if not key:
        print("FAIL: DASHSCOPE_API_KEY is empty in .env — paste your key first.")
        return 1

    router = ModelRouter()
    qwen = router.backends["qwen"]
    print(f"backend=qwen endpoint={qwen.base_url}")

    for model in ("qwen-turbo", "qwen-plus"):
        msgs = [
            Message("system", "You are a terse trading assistant."),
            Message("user", "In one sentence: what is a stop-loss order?"),
        ]
        try:
            reply = await qwen.complete(msgs, model=model, max_tokens=80, timeout=60)
        except Exception as exc:  # noqa: BLE001 — smoke test surfaces the raw error
            print(f"FAIL [{model}]: {type(exc).__name__}: {exc}")
            return 1
        print(f"OK   [{model}]: {reply.strip()[:200]}")

    print("\nPASS: Qwen Cloud reachable through the agent router.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
