"""Web-first scraping, weather, and vision tools — offline-deterministic checks."""

from __future__ import annotations

import pytest

from core.blackboard import Blackboard
from tools import vision, web
from tools.data_tools import build_data_registry


def test_strip_html_drops_scripts() -> None:
    html = "<html><head><style>x{}</style></head><body><script>evil()</script><p>Hello world</p></body></html>"
    out = web._strip_html(html)
    assert "Hello world" in out
    assert "evil" not in out and "x{}" not in out


def test_new_tools_registered(tmp_path) -> None:
    reg = build_data_registry(Blackboard(path=tmp_path / "t.db"))
    for name in ["web_research", "web_fetch", "web_search", "weather", "weather_forecast",
                 "analyze_image"]:
        assert name in reg.available(), name


@pytest.mark.asyncio
async def test_web_research_disabled(monkeypatch) -> None:
    monkeypatch.setattr(web, "settings", lambda: {"agents": {"allow_web": False}})
    res = await web.web_research("anything")
    assert res["available"] is False


@pytest.mark.asyncio
async def test_vision_disabled_without_model(monkeypatch) -> None:
    monkeypatch.setattr(vision, "models_config", lambda: {"vision": {"model": ""}})
    assert vision.vision_available() is False
    res = await vision.analyze_image("http://x/y.png")
    assert res["available"] is False


def test_vision_available_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(vision, "models_config", lambda: {"vision": {"model": "qwen-vl"}})
    assert vision.vision_available() is True
