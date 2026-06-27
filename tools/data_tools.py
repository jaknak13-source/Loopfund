"""Assembles the full tool registry from all free data adapters. Agents call
these by name through the registry, so every call is logged as a ToolCall.
"""

from __future__ import annotations

from core.blackboard import Blackboard
from tools import (
    altsignals,
    code_runner,
    filings,
    fx,
    ideation,
    macro,
    market,
    news,
    skills,
    social,
    universe_tools,
    valuation,
    vision,
    weather,
    web,
)
from tools.registry import ToolRegistry, default_registry


def build_data_registry(blackboard: Blackboard | None = None) -> ToolRegistry:
    reg = default_registry(blackboard)  # includes 'echo'

    # market
    reg.register("price", market.get_price)
    reg.register("history", market.get_history)
    reg.register("fundamentals", market.get_fundamentals)
    # fx
    reg.register("fx_rate", fx.fx_rate)
    # macro
    reg.register("fred_series", macro.fred_series)
    reg.register("macro_snapshot", macro.macro_snapshot)
    # news
    reg.register("rss_headlines", news.rss_headlines)
    reg.register("gdelt_search", news.gdelt_search)
    # social
    reg.register("reddit_hot", social.reddit_hot)
    reg.register("stocktwits_symbol", social.stocktwits_symbol)
    # filings + real SEC XBRL fundamentals
    reg.register("recent_filings", filings.recent_filings)
    reg.register("sec_financials", filings.sec_financials)
    reg.register("insider_transactions", filings.insider_transactions)
    # web-first data gathering (primary): scrape + search + combined research
    reg.register("web_fetch", web.web_fetch)
    reg.register("web_search", web.web_search)
    reg.register("web_research", web.web_research)
    # free APIs (additions): weather (Open-Meteo, no key)
    reg.register("weather", weather.weather)
    reg.register("weather_forecast", weather.weather_forecast)
    # vision (optional second model): analyze charts/satellite/screenshots
    reg.register("analyze_image", vision.analyze_image)
    # alt public signals: Congress trades + Polymarket; and universe expansion
    reg.register("congress_trades", altsignals.congress_trades)
    reg.register("polymarket_markets", altsignals.polymarket_markets)
    reg.register("propose_ticker", universe_tools.propose_ticker)
    # ideation fuel for creative agents: random past memory to spark connections
    reg.register("random_memory", ideation.random_memory)
    # fair value (DCF + multiples on real SEC data) + skill playbooks
    reg.register("estimate_fair_value", valuation.estimate_fair_value)
    reg.register("get_skill", skills.get_skill)
    reg.register("list_skills", skills.list_skills)
    reg.register("propose_skill", skills.propose_skill)  # agents codify/improve their own playbooks
    # self-taught research: code execution (self-gated by settings flag)
    reg.register("run_python", code_runner.run_python)

    _load_plugins(reg)
    return reg


def _load_plugins(reg: ToolRegistry) -> None:
    """Auto-discover extra tools: any tools/plugins/*.py module that defines
    `register(reg)` is loaded. Drop a file in to add tools — no core edits."""
    import importlib.util
    from pathlib import Path

    from core.logging import get_logger

    log = get_logger("plugins")
    plugins_dir = Path(__file__).resolve().parent / "plugins"
    if not plugins_dir.exists():
        return
    for path in sorted(plugins_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"tools.plugins.{path.stem}", path)
            if not spec or not spec.loader:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "register"):
                mod.register(reg)
                log.info("plugin_loaded", name=path.stem)
        except Exception as exc:  # a bad plugin must not break startup
            log.error("plugin_failed", name=path.stem, error=f"{type(exc).__name__}: {exc}")
