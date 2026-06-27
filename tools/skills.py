"""Skills: reusable markdown procedure playbooks (skills/*.md) that agents can pull
into their reasoning to follow a rigorous, consistent procedure (how to value a
stock, read an earnings report, spot a crash, verify evidence, trace cross-market
chains, find niche multi-baggers). Drop a .md in skills/ to add one — no code."""

from __future__ import annotations

import re

from core.config import ROOT
from core.logging import get_logger

log = get_logger("skills")
SKILLS_DIR = ROOT / "skills"

_MAX_SKILL_BODY = 6000        # cap a skill's size (prompt-budget + sanity)
_MAX_AUTHORED_SKILLS = 80     # cap agent-authored skills so the library can't grow unbounded
_AUTHORED_MARK = "<!-- agent-authored"


def _names() -> list[str]:
    if not SKILLS_DIR.exists():
        return []
    return sorted(p.stem for p in SKILLS_DIR.glob("*.md"))


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", str(name).strip().lower()).strip("-")[:48]


def _is_authored(path) -> bool:
    try:
        return _AUTHORED_MARK in path.read_text(encoding="utf-8")[:200]
    except Exception:
        return False


async def list_skills() -> dict:
    return {"skills": _names()}


async def propose_skill(name: str, body: str, rationale: str = "") -> dict:
    """Let an agent codify a reusable procedure it found valuable into a NEW skill
    playbook (or improve one it previously authored), so the knowledge is passed on to
    every agent via `get_skill`. Safety: name is slugged and dir-confined (no path
    traversal), body is injection-neutralized and size-capped, core (human-authored)
    skills can never be overwritten, and the agent-authored library is count-capped."""
    from core.sanitize import neutralize
    if not name or not body or len(body.strip()) < 80:
        return {"ok": False, "reason": "need a name and a substantive body (>=80 chars)"}
    slug = _slug(name)
    if not slug:
        return {"ok": False, "reason": "invalid name"}
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    path = SKILLS_DIR / f"{slug}.md"
    existed = path.exists()
    if existed and not _is_authored(path):
        return {"ok": False, "reason": f"'{slug}' is a core skill; choose a different name"}
    if not existed:
        authored = sum(1 for p in SKILLS_DIR.glob("*.md") if _is_authored(p))
        if authored >= _MAX_AUTHORED_SKILLS:
            return {"ok": False, "reason": f"agent-authored skill cap reached ({_MAX_AUTHORED_SKILLS})"}
    safe = neutralize(body)[:_MAX_SKILL_BODY]
    header = (f"# Skill: {name.strip()[:80]}\n\n{_AUTHORED_MARK}; "
              f"rationale: {neutralize(rationale)[:200]} -->\n\n")
    path.write_text(header + safe, encoding="utf-8")
    log.info("skill_proposed", name=slug, new=not existed)
    return {"ok": True, "name": slug, "path": str(path), "improved": existed}


async def get_skill(name: str) -> dict:
    """Return the procedure text for a named skill (case-insensitive). If not found,
    returns the list of available skills so the agent can pick one."""
    if not name:
        return {"available": False, "skills": _names()}
    key = name.strip().lower().replace(" ", "-")
    for p in SKILLS_DIR.glob("*.md") if SKILLS_DIR.exists() else []:
        if p.stem.lower() == key:
            return {"name": p.stem, "procedure": p.read_text(encoding="utf-8")[:6000], "source": "skill"}
    return {"available": False, "requested": name, "skills": _names()}
