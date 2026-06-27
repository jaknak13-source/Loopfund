"""Persist quant model outputs as structured JSON artifacts so runs are
reproducible and auditable. Artifacts live under quant/scripts/artifacts/.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from core.config import ROOT

ARTIFACT_DIR = ROOT / "quant" / "scripts" / "artifacts"


def save_artifact(name: str, payload: dict) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    path = ARTIFACT_DIR / f"{ts}_{safe}.json"
    record = {"name": name, "created_at": datetime.now(timezone.utc).isoformat(), "payload": payload}
    path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    return path
