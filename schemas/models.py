"""Core data contracts for the system. Every agent input/output is one of these.

Design notes:
- Confidence is always a range, never a bare float (anti false-precision rule).
- Every factual claim carries a Citation; unverified claims are tracked explicitly.
- IDs are caller-supplied strings (ULID/uuid) so records are reproducible in tests.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Confidence(BaseModel):
    """Calibrated probability with an explicit uncertainty band."""

    score: float = Field(ge=0.0, le=1.0)
    low: float = Field(ge=0.0, le=1.0)
    high: float = Field(ge=0.0, le=1.0)
    rationale: str = ""

    @model_validator(mode="after")
    def _check_band(self) -> "Confidence":
        if not (self.low <= self.score <= self.high):
            raise ValueError(f"confidence band invalid: low={self.low} score={self.score} high={self.high}")
        return self


class Citation(BaseModel):
    """A single sourced claim. `verified` gates whether it may raise confidence."""

    source: str  # url / filing id / dataset name
    claim: str
    verified: bool = False
    primary: bool = False  # primary source (filing/official/exchange) vs secondary
    retrieved_at: datetime


class ToolCall(BaseModel):
    """An invocation of a registered tool/data adapter. Always logged."""

    id: str
    agent: str
    tool: str
    params: dict = Field(default_factory=dict)
    started_at: datetime
    finished_at: datetime | None = None
    ok: bool | None = None
    attempts: int = 1
    error: str | None = None
    output_ref: str | None = None  # path/id of stored output; never inline blobs


Stance = Literal["bullish", "bearish", "neutral", "uncertain"]


class AgentReport(BaseModel):
    """A unit of analysis written by one agent to the blackboard."""

    id: str
    agent: str
    cycle_id: str
    created_at: datetime
    topic: str
    assets: list[str] = Field(default_factory=list)
    stance: Stance = "uncertain"
    summary: str
    findings: list[str] = Field(default_factory=list)
    confidence: Confidence
    citations: list[Citation] = Field(default_factory=list)
    unverified_claims: list[str] = Field(default_factory=list)
    # Deterministic, stance-independent per-asset signal in [-1, 1] (e.g. QuantAgent's
    # Kelly/expected-return tilt or a valuation margin-of-safety). Aggregated directly
    # so a weak model's neutral stance cannot zero out a real numeric edge.
    asset_signals: dict[str, float] = Field(default_factory=dict)
    model_used: str = ""
    tool_calls: list[str] = Field(default_factory=list)  # ToolCall ids


class TradeAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    TRIM = "trim"
    ADD = "add"
    HOLD = "hold"
    HEDGE = "hedge"
    NO_ACTION = "no_action"


class PortfolioDecision(BaseModel):
    """The single consolidated decision emitted per cooldown window."""

    id: str
    decision_date: date
    # precise creation time — decision_date is date-only, so without this every
    # same-day decision rendered the identical timestamp (and sorted unstably).
    # Real decisions set this explicitly (DecisionAgent); records missing it (older
    # rows) fall back to decision_date below rather than the read-time, so they don't shift.
    created_at: datetime | None = None
    action: TradeAction
    asset: str | None = None
    target_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    size_eur: float | None = None
    reasoning: str
    key_assumptions: list[str] = Field(default_factory=list)
    known_risks: list[str] = Field(default_factory=list)
    confidence: Confidence
    contributing_reports: list[str] = Field(default_factory=list)  # AgentReport ids
    risk_rebuttal: str = ""  # RiskAgent challenge + how it was resolved
    mode: Literal["dry", "live"] = "dry"
    human_override: str | None = None
    # Extra high-conviction buys to open IN THE SAME cycle (beyond the primary `asset`).
    # The DecisionAgent only fills this when several names independently clear the bar;
    # each entry is corroboration- + cap- + fee-checked before execution. Items:
    # {"asset": str, "target_weight": 0-1, "reasoning": str}.
    additional_buys: list[dict] = Field(default_factory=list)
    # structured 'why no trade' so the dashboard can tally blockers instead of parsing prose
    block_reason: Literal[
        "traded", "risk_veto", "below_floor", "no_structured_output",
        "evidence_insufficient", "model_no_action"
    ] | None = None

    @model_validator(mode="before")
    @classmethod
    def _fill_created_at(cls, data: object) -> object:
        # older stored decisions have no created_at -> fall back to the date (midnight)
        # so they render their original day, never the (shifting) read-time.
        if isinstance(data, dict) and not data.get("created_at") and data.get("decision_date"):
            data["created_at"] = data["decision_date"]
        return data


class SimulatedTrade(BaseModel):
    """A simulated fill in the dry-mode ledger. Real prices, realistic EUR fees."""

    id: str
    decision_id: str
    placed_at: datetime
    asset: str
    side: Literal["buy", "sell"]
    qty: float
    ccy: str = "EUR"  # asset's native currency
    price_native: float  # price in asset's native ccy
    fx_rate: float = 1.0  # native -> EUR at fill time
    fill_price_eur: float | None = None
    fees_eur: float = 0.0
    status: Literal["pending", "filled", "rejected", "closed"] = "pending"
    realized_pnl_eur: float | None = None
    unrealized_pnl_eur: float | None = None
    closed_at: datetime | None = None


class MemoryEntry(BaseModel):
    """One item in the persistent RAG memory."""

    id: str
    created_at: datetime
    kind: Literal[
        "report", "decision", "lesson", "summary", "hypothesis", "news", "model_output",
        "research",
    ]
    title: str
    body: str
    assets: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    confidence: float | None = None
    outcome: Literal["correct", "incorrect", "partial", "pending", "unknown"] = "pending"
    refs: list[str] = Field(default_factory=list)  # linked entry ids
    embedding_id: str | None = None


class ActivityEvent(BaseModel):
    """A real-time activity record for the dashboard 'Mind' tab: what an agent is
    doing/thinking, a research note, a decision, or a status/error. Append-only,
    bounded + pruned like a log. Cheap to write (no extra LLM calls — built from
    text the system already produced)."""

    id: str
    ts: datetime
    cycle_id: str = ""
    agent: str = ""
    kind: Literal["status", "thinking", "research", "decision", "tool", "error"] = "status"
    title: str = ""
    summary: str = ""
    meta: dict = Field(default_factory=dict)


class HumanInstruction(BaseModel):
    """A message dropped into the loop by the human. Always high priority."""

    id: str
    received_at: datetime
    text: str
    parsed_intent: str | None = None  # e.g. "defensive_30d", "avoid:crypto", "no_trade_week"
    priority: Literal["high"] = "high"
    active: bool = True
    expires_at: datetime | None = None
