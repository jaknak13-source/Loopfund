"""Routes each agent to its configured backend/model and SERIALIZES all inference.

The semaphore (default size 1) is the M4 Air crash guard: only one LLM call runs
at a time across the whole system, regardless of how many agents are active.
Backends can be injected for tests (e.g. MockBackend).
"""

from __future__ import annotations

import asyncio
from typing import Any

from core.config import env, models_config, settings
from core.logging import get_logger
from models_adapter.anthropic import AnthropicBackend
from models_adapter.base import LLMBackend, Message
from models_adapter.gemini import GeminiBackend
from models_adapter.lmstudio import LMStudioBackend
from models_adapter.openai_compat import OpenAICompatBackend
from models_adapter.qwen import QwenBackend

log = get_logger("router")

# name -> (default base URL, env var for base URL, env var for API key, key-required?)
# Every OpenAI-compatible preset is built from one universal class. Local presets
# need no key; cloud presets do. Point any preset at another host via its env var.
_OPENAI_PRESETS: dict[str, tuple[str, str, str, bool]] = {
    "local":      ("http://localhost:1234/v1",       "LOCAL_BASE_URL",      "LOCAL_API_KEY",      False),
    "ollama":     ("http://localhost:11434/v1",       "OLLAMA_BASE_URL",     "OLLAMA_API_KEY",     False),
    "vllm":       ("http://localhost:8000/v1",        "VLLM_BASE_URL",       "VLLM_API_KEY",       False),
    "openai":     ("https://api.openai.com/v1",        "OPENAI_BASE_URL",     "OPENAI_API_KEY",     True),
    "openrouter": ("https://openrouter.ai/api/v1",     "OPENROUTER_BASE_URL", "OPENROUTER_API_KEY", True),
    "groq":       ("https://api.groq.com/openai/v1",   "GROQ_BASE_URL",       "GROQ_API_KEY",       True),
    "together":   ("https://api.together.xyz/v1",      "TOGETHER_BASE_URL",   "TOGETHER_API_KEY",   True),
    "deepseek":   ("https://api.deepseek.com/v1",      "DEEPSEEK_BASE_URL",   "DEEPSEEK_API_KEY",   True),
    "mistral":    ("https://api.mistral.ai/v1",        "MISTRAL_BASE_URL",    "MISTRAL_API_KEY",    True),
    "xai":        ("https://api.x.ai/v1",              "XAI_BASE_URL",        "XAI_API_KEY",        True),
}


class ModelRouter:
    def __init__(
        self,
        backends: dict[str, LLMBackend] | None = None,
        max_concurrent: int | None = None,
    ) -> None:
        inf = settings().get("inference", {})
        self._sem = asyncio.Semaphore(max_concurrent or int(inf.get("max_concurrent", 1)))
        self._timeout = float(inf.get("request_timeout_s", 180))
        self.backends = backends or self._default_backends()
        self.models_cfg = models_config()

    @staticmethod
    def _default_backends() -> dict[str, LLMBackend]:
        """Build every supported backend from environment variables.

        Backends are created lazily-cheap (no network on construction). A backend
        only errors when actually called without its required key, so registering
        them all is free even if most keys are blank.
        """
        backends: dict[str, LLMBackend] = {}
        # Universal OpenAI-compatible presets (local + every major cloud).
        for name, (default_url, url_var, key_var, requires_key) in _OPENAI_PRESETS.items():
            backends[name] = OpenAICompatBackend(
                env(url_var, default_url) or default_url,
                env(key_var, "") or "",
                name=name,
                requires_key=requires_key,
            )
        # Back-compat aliases for the original two backends.
        lm_url = env("LMSTUDIO_BASE_URL", "http://localhost:1234/v1") or ""
        lm_key = env("LMSTUDIO_API_KEY", "lm-studio") or "lm-studio"
        backends["lmstudio"] = LMStudioBackend(lm_url, lm_key)
        backends["qwen"] = QwenBackend(env("QWEN_BASE_URL", "") or None, env("DASHSCOPE_API_KEY", "") or "")
        # Native (non-OpenAI-shaped) cloud backends.
        backends["anthropic"] = AnthropicBackend(
            env("ANTHROPIC_BASE_URL", "") or None, env("ANTHROPIC_API_KEY", "") or ""
        )
        backends["gemini"] = GeminiBackend(
            env("GEMINI_BASE_URL", "") or None,
            env("GEMINI_API_KEY", "") or env("GOOGLE_API_KEY", "") or "",
        )
        return backends

    def resolve(self, agent: str, profile: str = "default") -> dict[str, Any]:
        cfg = self.models_cfg
        spec = dict(cfg.get(profile) or cfg["default"])
        spec.update(cfg.get("agents", {}).get(agent, {}))
        return spec

    async def complete(
        self,
        agent: str,
        messages: list[Message],
        profile: str = "default",
    ) -> str:
        spec = self.resolve(agent, profile)
        backend_name = spec.get("backend", "local")
        backend = self.backends.get(backend_name)
        if backend is None:
            # If exactly one backend is registered, just use it — a single-backend
            # setup (or an injected test backend) shouldn't have to match the name
            # configured in models.yaml.
            if len(self.backends) == 1:
                backend = next(iter(self.backends.values()))
                log.warning("backend_fallback", requested=backend_name, using=getattr(backend, "name", "?"))
            else:
                raise ValueError(
                    f"backend '{backend_name}' not available for agent '{agent}' "
                    f"(have: {sorted(self.backends)})"
                )
        # Some models (e.g. Gemma) reject a separate "system" role. Fold system
        # content into the first user message when the model can't take it.
        if not bool(spec.get("supports_system_role", True)):
            messages = _merge_system_into_user(messages)

        # read the timeout live so it's hot-reloadable from the Settings tab (no restart)
        timeout = float(settings().get("inference", {}).get("request_timeout_s", self._timeout))
        async with self._sem:  # serialized inference — one model call at a time
            log.info("inference", agent=agent, backend=backend_name, model=spec.get("model"))
            return await backend.complete(
                messages,
                model=spec["model"],
                temperature=float(spec.get("temperature", 0.3)),
                max_tokens=int(spec.get("max_tokens", 2048)),
                timeout=timeout,
            )


def _merge_system_into_user(messages: list[Message]) -> list[Message]:
    """Combine system messages into the first user message; preserve order otherwise."""
    system_text = "\n\n".join(m.content for m in messages if m.role == "system")
    rest = [m for m in messages if m.role != "system"]
    if not system_text:
        return rest or messages
    for i, m in enumerate(rest):
        if m.role == "user":
            rest[i] = Message("user", f"{system_text}\n\n---\n\n{m.content}")
            return rest
    # no user message: send the system text as a user turn
    return [Message("user", system_text), *rest]
