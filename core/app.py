"""Composition root: build the real Orchestrator from config + live components.
Used by the dashboard server and the CLI entrypoint. Tests build their own
offline orchestrator instead of calling this.
"""

from __future__ import annotations

from core.blackboard import Blackboard
from core.config import env, models_config, settings
from core.orchestrator import Orchestrator
from execution.portfolio import PortfolioStore
from execution.sim_ledger import SimLedger
from memory.embeddings import HashingEmbedder, LMStudioEmbedder
from memory.rag import RagMemory
from models_adapter.router import ModelRouter
from tools.data_tools import build_data_registry

DEFAULT_WATCHLIST = ["SPY", "QQQ", "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "XOM", "GLD", "BTC-USD"]


def _build_embedder():
    """Use LM Studio embeddings if configured, else the offline hashing embedder."""
    emb_model = models_config().get("embeddings", {}).get("model")
    if emb_model:
        return LMStudioEmbedder(
            base_url=env("LMSTUDIO_BASE_URL", "http://localhost:1234/v1") or "",
            model=emb_model,
            api_key=env("LMSTUDIO_API_KEY", "lm-studio") or "lm-studio",
        )
    return HashingEmbedder()


def _select_execution(tools, ledger):
    """Dry by default. Live requires mode=live AND env LOOPFUND_ALLOW_LIVE=1, and
    even then uses the (unimplemented) LiveExecution so it fails loudly — no
    accidental real orders."""
    from execution.dry import DryExecution

    mode = settings().get("mode", "dry")
    if mode == "live":
        if env("LOOPFUND_ALLOW_LIVE") != "1":
            raise RuntimeError(
                "mode=live but LOOPFUND_ALLOW_LIVE != 1. Refusing to start. "
                "The system is dry-mode only until you deliberately enable live."
            )
        from execution.live import LiveExecution
        return LiveExecution()
    return DryExecution(tools, ledger)


def build_orchestrator(watchlist: list[str] | None = None) -> Orchestrator:
    bb = Blackboard()
    rag = RagMemory(bb, embedder=_build_embedder())
    store = PortfolioStore()
    ledger = SimLedger(store.load(), store=store, blackboard=bb)
    router = ModelRouter()  # real LM Studio backend
    tools = build_data_registry(bb)
    wl = watchlist or list(settings().get("watchlist", DEFAULT_WATCHLIST))
    execution = _select_execution(tools, ledger)
    return Orchestrator(blackboard=bb, router=router, data_tools=tools, rag=rag,
                        ledger=ledger, watchlist=wl, execution=execution)
