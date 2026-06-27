"""Local-only FastAPI dashboard backend. Exposes portfolio, decisions, trades,
agent activity, memory search, settings, human chat (instructions), and loop
control. Binds to localhost only.

create_app(orchestrator) takes a prebuilt orchestrator (tests inject an offline
one). The CLI entrypoint builds the real one via core.app.build_orchestrator().
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.config import env, models_config, persist_env, reload, risk_limits, settings, update_config
from core.cost import cost_meter
from core.instructions import parse_intent
from core.loop_runner import LoopRunner
from schemas import HumanInstruction


# Which env var holds the API key for each backend the router knows about.
# Backends not listed here (local/ollama/vllm) need no key.
_BACKEND_KEY_VAR: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "groq": "GROQ_API_KEY",
    "together": "TOGETHER_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "xai": "XAI_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "lmstudio": "LMSTUDIO_API_KEY",
}


class InstructionIn(BaseModel):
    text: str


class ApiKeyIn(BaseModel):
    key: str
    base_url: str | None = None  # optional endpoint override
    backend: str | None = None   # which backend to set the key for; default = active one


class SettingsPatch(BaseModel):
    name: str  # settings | models | risk_limits
    patch: dict


class LoopStart(BaseModel):
    interval_seconds: int | None = None


class BriefingIn(BaseModel):
    name: str
    body: str
    schedule: str = "cycle"
    profile: str = "default"
    tools: list[dict] = []
    enabled: bool = True


def create_app(orchestrator) -> FastAPI:
    orch = orchestrator
    loop = LoopRunner(orch)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Set LOOPFUND_AUTOLOOP=<seconds> to start the 24/7 loop on boot (used by the
        # launchd service) so the fund runs unattended without a manual dashboard click.
        iv = os.environ.get("LOOPFUND_AUTOLOOP")
        if iv and iv.isdigit():
            loop.start(int(iv))
        yield
        await loop.stop()

    app = FastAPI(title="loopfund dashboard", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"], allow_headers=["*"],
    )
    app.state.orchestrator = orch
    app.state.loop = loop

    @app.get("/api/health")
    async def health():
        spec = orch.router.resolve("DecisionAgent")
        backend_name = spec.get("backend", "local")
        key_var = _BACKEND_KEY_VAR.get(backend_name)
        # local backends need no key, so they count as "ready".
        key_set = (key_var is None) or bool((env(key_var, "") or "").strip())
        return {
            "status": "ok",
            "mode": settings().get("mode", "dry"),
            "model": spec.get("model"),
            "backend": backend_name,
            "backend_needs_key": key_var is not None,
            "key_set": key_set,
            "memory_size": orch.rag.size(),
            "watchlist": orch.watchlist,
            "loop": loop.status(),
            "can_trade_now": orch.can_trade_now(),
            "cost_usd": cost_meter().snapshot()["total_usd"],
            "time": datetime.now(timezone.utc).isoformat(),
        }

    @app.post("/api/apikey")
    async def set_api_key(body: ApiKeyIn):
        """Set an API key for a model backend from the dashboard so a user can paste it
        in the UI instead of editing files. Persists to .env (gitignored) and updates the
        live backend so cycles work immediately — no restart. The key is never returned
        or logged; only a masked confirmation.

        `backend` defaults to the currently active backend (from models.yaml). Local
        backends (local/ollama/vllm) need no key."""
        key = (body.key or "").strip()
        if not key:
            raise HTTPException(400, "empty key")
        backend_name = (body.backend or orch.router.resolve("DecisionAgent").get("backend", "local"))
        key_var = _BACKEND_KEY_VAR.get(backend_name)
        if key_var is None:
            raise HTTPException(400, f"backend '{backend_name}' does not use an API key")
        persist_env(key_var, key)
        if body.base_url and body.base_url.strip():
            # store the base-url override under the backend's *_BASE_URL convention
            url_var = key_var.replace("_API_KEY", "_BASE_URL").replace("DASHSCOPE_BASE_URL", "QWEN_BASE_URL")
            persist_env(url_var, body.base_url.strip())
        # update the live backend so the running fund uses the new key at once
        be = orch.router.backends.get(backend_name)
        if be is not None:
            be.api_key = key
            if body.base_url and body.base_url.strip():
                be.base_url = body.base_url.strip().rstrip("/")
        masked = key[:6] + "…" + key[-4:] if len(key) > 12 else "set"
        return {"set": True, "backend": backend_name, "masked": masked}

    @app.get("/api/portfolio")
    async def portfolio():
        snap = await orch.portfolio_snapshot()
        total = snap.get("total_value_eur") or 1.0
        positions = []
        for a, p in orch.ledger.p.positions.items():
            cur_eur = None
            native = None
            try:
                q = await orch.execution._quote(a)
                if q:
                    cur_eur, native, _ccy, _fx = q
            except Exception:
                pass
            val = (cur_eur or p.avg_cost_eur) * p.qty
            positions.append({
                "asset": a, "qty": p.qty, "avg_cost_eur": p.avg_cost_eur, "ccy": p.ccy,
                "current_price_eur": cur_eur, "current_price_native": native,
                "value_eur": round(val, 2), "weight_pct": round(100.0 * val / total, 1),
                "unrealized_eur": round(((cur_eur or p.avg_cost_eur) - p.avg_cost_eur) * p.qty, 2),
            })
        positions.sort(key=lambda x: x["weight_pct"], reverse=True)
        cash_pct = round(100.0 * snap.get("cash_eur", 0) / total, 1)
        # Cash-only baseline: total capital contributed (initial + top-ups). Compare to
        # current value to see what you'd have if you'd never invested anything.
        contributed = round(orch.learning.contributed_capital(), 2)
        vs_cash = round(total - contributed, 2)
        return {"snapshot": snap, "positions": positions,
                "cash_weight_pct": cash_pct, "invested_pct": round(100.0 - cash_pct, 1),
                "contributed_eur": contributed, "vs_cash_eur": vs_cash,
                "vs_cash_pct": round(100.0 * vs_cash / contributed, 2) if contributed else 0.0}

    @app.get("/api/cost")
    async def cost():
        """Cumulative Qwen Cloud token spend (USD) since this process started, by model."""
        from core.cost import cost_meter
        return cost_meter().snapshot()

    @app.get("/api/calibration")
    async def calibration():
        """Learned agent/source trust + SP500 benchmark."""
        snap = await orch.portfolio_snapshot()
        spy = await orch._price_eur(orch.benchmark_symbol)
        return {
            "benchmark": orch.learning.benchmark(spy, snap["total_value_eur"]),
            "horizon_days": orch.horizon_days,
            **orch.learning.metrics_snapshot(),
        }

    @app.get("/api/decisions")
    async def decisions(limit: int = 30):
        return [d.model_dump(mode="json") for d in orch.bb.latest_decisions(limit)]

    @app.get("/api/trades")
    async def trades(limit: int = 50):
        return [t.model_dump(mode="json") for t in orch.bb.latest_trades(limit)]

    @app.get("/api/reports")
    async def reports(limit: int = 50):
        return [r.model_dump(mode="json") for r in orch.bb.recent_reports(limit)]

    @app.get("/api/activity")
    async def activity(agent: str = "", kind: str = "", q: str = "", cycle_id: str = "",
                       limit: int = 100):
        """Real-time feed for the Mind tab: agent thinking, research, decisions, status."""
        evs = orch.bb.latest_activity(agent=agent, kind=kind, q=q, cycle_id=cycle_id, limit=limit)
        return [e.model_dump(mode="json") for e in evs]

    @app.get("/api/cycle/progress")
    async def cycle_progress():
        """Live per-agent state for the current/last cycle (derived from status events)."""
        evs = orch.bb.latest_activity(limit=150)
        cyc = next((e.cycle_id for e in evs if e.cycle_id), "")
        cev = [e for e in evs if e.cycle_id == cyc]
        agents: dict[str, dict] = {}
        for e in reversed(cev):  # oldest -> newest so latest state wins
            if e.agent in ("Orchestrator", "ResearchLoop"):
                continue
            if e.kind == "status" and e.meta.get("state") == "running":
                agents[e.agent] = {"name": e.agent, "state": "running", "at": e.ts.isoformat()}
            elif e.kind == "thinking":
                agents[e.agent] = {"name": e.agent, "state": "done",
                                   "stance": e.meta.get("stance"),
                                   "confidence": e.meta.get("confidence"), "at": e.ts.isoformat()}
            elif e.kind == "error":
                agents[e.agent] = {"name": e.agent, "state": "error", "at": e.ts.isoformat()}
        # staleness: if the newest event overall isn't this cycle's (e.g. research is now
        # running, or the process restarted mid-cycle), nothing is actively "running".
        newest = evs[0] if evs else None
        stale = (newest is None) or (newest.cycle_id != cyc) or (newest.kind == "research")
        current = None if stale else next(
            (e.agent for e in cev
             if e.kind == "status" and e.meta.get("state") == "running"
             and agents.get(e.agent, {}).get("state") == "running"), None)
        phase = ("idle" if stale else
                 ("deciding" if any(e.kind == "decision" for e in cev) else "analysis"))
        return {"cycle_id": cyc, "phase": phase, "current_agent": current,
                "agents": list(agents.values()), "loop": loop.status().get("mode")}

    @app.get("/api/tool_calls")
    async def tool_calls(limit: int = 100, cycle_id: str = ""):
        rows = orch.bb.store._query("tool_calls", limit=limit)
        return {"tool_calls": rows}

    @app.get("/api/decisions/blockers")
    async def decision_blockers(limit: int = 200):
        """Tally why decisions did/didn't trade — the why-no-trade explainer."""
        ds = orch.bb.latest_decisions(limit)
        tally: dict[str, int] = {}
        for d in ds:
            key = d.block_reason or ("traded" if d.action.value != "no_action" else "model_no_action")
            tally[key] = tally.get(key, 0) + 1
        return {"blockers": tally, "n": len(ds)}

    @app.get("/api/agents")
    async def agents():
        recent = orch.bb.recent_reports(150)
        descriptions = {
            "ResearchAgent": ("news", "Scrapes & scores news (RSS/GDELT), cross-checks niche claims."),
            "MacroAgent": ("macro", "Rates, inflation, FX, commodities, geopolitics, regime."),
            "FundamentalsAgent": ("fundamentals", "Valuation, margins, guidance, leverage, quality."),
            "SentimentAgent": ("sentiment", "Crowd/social sentiment; manipulation/hype risk."),
            "IpoMnaAgent": ("ipo/m&a", "IPOs, S-1/SPAC, mergers, where smart money moves."),
            "AltDataAgent": ("alt-data", "Hiring/patents/shipping proxies; honest on gaps."),
            "QuantAgent": ("quant", "Factors, Monte Carlo, regime, Kelly sizing."),
            "SmartMoneyAgent": ("smart money", "Follows politician + insider (Form-4) disclosed flows; signed per-ticker."),
            "RiskAgent": ("risk", "Skeptic: tail risk, downside, concentration, vetoes."),
            "QuantResearchAgent": ("research", "Writes/runs its own backtest code (idle)."),
            "MetaAgent": ("meta", "Authors new specialist agents (idle)."),
            "MemoryAuditorAgent": ("audit", "Re-verifies memory daily; flags stale/hallucinated."),
            "DecisionAgent": ("coordinator", "Evidence-weighted final decision + risk debate."),
        }
        core = list(descriptions)
        last_by_agent: dict[str, dict] = {}
        for r in recent:
            if r.agent not in last_by_agent:
                last_by_agent[r.agent] = {
                    "last_topic": r.topic, "stance": r.stance,
                    "confidence": r.confidence.score, "at": r.created_at.isoformat(),
                }

        def row(name: str, kind: str, desc: str, dynamic: bool, schedule: str = "cycle") -> dict:
            base = {"agent": name, "role": kind, "description": desc, "dynamic": dynamic,
                    "schedule": schedule, "last_topic": None, "at": None}
            base.update(last_by_agent.get(name, {}))
            return base

        out = [row(n, descriptions[n][0], descriptions[n][1], False) for n in core]
        try:
            from agents.briefing_loader import discover
            for b in discover():
                out.append(row(b.name, "custom", b.body[:120], True, b.schedule))
        except Exception:
            pass
        return out

    @app.get("/api/briefings")
    async def list_briefings():
        from agents.briefing_loader import discover
        return [
            {"name": b.name, "schedule": b.schedule, "enabled": b.enabled,
             "profile": b.profile, "tools": [t["name"] for t in b.tools],
             "body_preview": b.body[:400], "path": b.path}
            for b in discover()
        ]

    @app.post("/api/briefings")
    async def create_briefing(body: BriefingIn):
        import re

        import yaml

        from agents.briefing_loader import RESERVED, briefings_dir, discover
        from agents.dynamic import load_briefing

        name = body.name.strip()
        if not name or not body.body.strip():
            raise HTTPException(400, "name and body required")
        if name in RESERVED:
            raise HTTPException(400, f"'{name}' is a reserved core agent name")
        if any(b.name == name for b in discover()):
            raise HTTPException(400, f"agent '{name}' already exists")
        meta = {"name": name, "profile": ("dev" if body.profile == "dev" else "default"),
                "schedule": body.schedule if body.schedule in ("cycle", "idle", "off") else "cycle",
                "enabled": body.enabled, "tools": body.tools}
        content = "---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n" + body.body.strip() + "\n"
        slug = re.sub(r"[^A-Za-z0-9_-]", "_", name)[:48]
        path = briefings_dir() / f"{slug}.md"
        path.write_text(content, encoding="utf-8")
        if load_briefing(path) is None:
            path.unlink(missing_ok=True)
            raise HTTPException(400, "briefing failed validation")
        return {"created": name, "path": str(path)}

    @app.get("/api/errors")
    async def errors(limit: int = 50):
        from core.config import data_dir
        p = data_dir() / "errors.jsonl"
        if not p.exists():
            return {"errors": []}
        import json as _json
        lines = p.read_text(encoding="utf-8").splitlines()[-limit:]
        out = []
        for ln in lines:
            try:
                out.append(_json.loads(ln))
            except _json.JSONDecodeError:
                continue
        return {"errors": list(reversed(out))}

    @app.get("/api/market")
    async def market():
        quotes = []
        for a in orch.watchlist:
            try:
                q = await orch.execution._quote(a)
            except Exception:
                q = None
            if q:
                price_eur, native, ccy, fx = q
                quotes.append({"asset": a, "price_native": native, "ccy": ccy,
                               "fx_to_eur": fx, "price_eur": round(price_eur, 4)})
            else:
                quotes.append({"asset": a, "price_eur": None, "unavailable": True})
        return {"quotes": quotes, "watchlist": orch.watchlist}

    @app.get("/api/memory")
    async def memory(q: str = "", k: int = 8, kind: str | None = None):
        if not q:
            return {"size": orch.rag.size(), "results": []}
        hits = orch.rag.search(q, k=k, kind=kind)
        return {"size": orch.rag.size(),
                "results": [h.model_dump(mode="json") for h in hits]}

    @app.get("/api/settings")
    async def get_settings():
        return {"settings": settings(), "models": models_config(), "risk_limits": risk_limits()}

    @app.put("/api/settings")
    async def put_settings(body: SettingsPatch):
        try:
            merged = update_config(body.name, body.patch)
        except KeyError as exc:
            raise HTTPException(400, str(exc))
        return {"updated": body.name, "value": merged}

    @app.get("/api/instructions")
    async def get_instructions():
        return [i.model_dump(mode="json") for i in orch.bb.active_instructions()]

    @app.post("/api/instructions")
    async def post_instruction(body: InstructionIn):
        instr = HumanInstruction(
            id=str(uuid.uuid4()), received_at=datetime.now(timezone.utc),
            text=body.text, parsed_intent=parse_intent(body.text),
        )
        orch.bb.write_instruction(instr)
        return instr.model_dump(mode="json")

    @app.post("/api/cycle/run")
    async def run_cycle():
        return await orch.run_cycle()

    @app.get("/api/loop/status")
    async def loop_status():
        return loop.status()

    @app.post("/api/loop/start")
    async def loop_start(body: LoopStart):
        return loop.start(body.interval_seconds)

    @app.post("/api/loop/stop")
    async def loop_stop():
        return await loop.stop()

    @app.get("/api/backups")
    async def backups():
        from core.backup import list_backups
        return {"backups": list_backups()}

    @app.post("/api/backups")
    async def make_backup():
        from core.backup import backup_now
        return {"created": str(backup_now(tag="manual"))}

    @app.post("/api/backups/restore")
    async def restore_backup(body: dict):
        from core.backup import restore
        name = str(body.get("name", ""))
        if not restore(name):
            raise HTTPException(404, f"backup '{name}' not found")
        return {"restored": name, "note": "restart the loop to load restored state"}

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built React dashboard from the same origin as the API.

    With this, `./start.sh` is the *only* command a user needs: the backend serves
    both /api and the UI on one port. If the frontend hasn't been built yet (no
    dist/), the API still runs and the root path explains how to build it. The dev
    workflow (Vite on :5173 proxying /api) is unaffected.
    """
    from pathlib import Path

    from fastapi.responses import JSONResponse
    from fastapi.staticfiles import StaticFiles

    dist = Path(__file__).resolve().parents[1] / "web" / "dist"
    if dist.is_dir() and (dist / "index.html").exists():
        # html=True makes unknown paths fall back to index.html (SPA routing).
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")
    else:
        @app.get("/")
        async def _frontend_missing():
            return JSONResponse(
                {
                    "status": "ok",
                    "frontend": "not built",
                    "hint": "Run ./start.sh (start.bat on Windows), or with Node "
                            "installed: cd dashboard/web && npm install && npm run build. "
                            "The API is live at /api/health.",
                },
                status_code=200,
            )


def build_default_app() -> FastAPI:
    """Production app: builds the real orchestrator (needs a model backend for cycles)."""
    from core.app import build_orchestrator

    reload()
    return create_app(build_orchestrator())
