"""Vision tool: analyze an image (chart, satellite tile, screenshot, scanned doc)
with a vision-capable model. Uses a SEPARATE model configured under the `vision`
profile in models.yaml (the main reasoning model need not be multimodal). Disabled
gracefully until a vision model id is set.

The model's answer about an image is UNTRUSTED interpretation — agents must treat
it as a lead to verify, not ground truth (charts can be misread).
"""

from __future__ import annotations

import httpx

from core.config import env, models_config
from core.logging import get_logger

log = get_logger("vision")


def _vision_spec() -> dict:
    return models_config().get("vision", {}) or {}


def vision_available() -> bool:
    return bool(_vision_spec().get("model"))


async def analyze_image(image_url: str, question: str = "Describe what is shown and any data/values.") -> dict:
    """image_url: http(s) URL or a data: URI. Returns the vision model's reading."""
    spec = _vision_spec()
    model = spec.get("model")
    if not model:
        return {"available": False, "reason": "no vision model configured (models.yaml: vision.model)"}
    base = (env("LMSTUDIO_BASE_URL", "http://localhost:1234/v1") or "").rstrip("/")
    payload = {
        "model": model,
        "max_tokens": int(spec.get("max_tokens", 600)),
        "temperature": float(spec.get("temperature", 0.2)),
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }],
    }
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{base}/chat/completions", json=payload,
                             headers={"Authorization": f"Bearer {env('LMSTUDIO_API_KEY','lm-studio')}"})
            r.raise_for_status()
            data = r.json()
        return {"image_url": image_url, "analysis": data["choices"][0]["message"]["content"],
                "model": model, "source": "vision", "verified": False}
    except Exception as exc:
        log.warning("vision_failed", error=str(exc))
        return {"available": False, "error": str(exc)}
