"""Agent-authored skills: agents codify proven procedures into the shared playbook
library (the compounding-knowledge loop), safely."""

from __future__ import annotations

import asyncio


def test_propose_skill_creates_and_is_retrievable(monkeypatch, tmp_path):
    import tools.skills as skills
    monkeypatch.setattr(skills, "SKILLS_DIR", tmp_path)
    body = ("# Steps\n1. Pull fair value.\n2. Check corroboration.\n3. Size by edge.\n"
            "This is a generalizable, reusable procedure with enough substance to store.")
    res = asyncio.run(skills.propose_skill("My New Edge Play", body, rationale="worked 3x"))
    assert res["ok"] and res["name"] == "my-new-edge-play"
    got = asyncio.run(skills.get_skill("my new edge play"))  # case/space-insensitive
    assert got.get("source") == "skill" and "Size by edge" in got["procedure"]
    assert "my-new-edge-play" in asyncio.run(skills.list_skills())["skills"]


def test_propose_skill_cannot_overwrite_core(monkeypatch, tmp_path):
    import tools.skills as skills
    monkeypatch.setattr(skills, "SKILLS_DIR", tmp_path)
    (tmp_path / "valuation-playbook.md").write_text("# Skill: Valuation\nhuman-written core",
                                                    encoding="utf-8")
    res = asyncio.run(skills.propose_skill("valuation-playbook", "x" * 100))
    assert res["ok"] is False and "core" in res["reason"]
    assert (tmp_path / "valuation-playbook.md").read_text(encoding="utf-8") == \
        "# Skill: Valuation\nhuman-written core"  # untouched


def test_propose_skill_can_improve_own_authored(monkeypatch, tmp_path):
    import tools.skills as skills
    monkeypatch.setattr(skills, "SKILLS_DIR", tmp_path)
    asyncio.run(skills.propose_skill("flow-edge", "v1 body " * 20))
    res = asyncio.run(skills.propose_skill("flow-edge", "v2 improved body " * 20))
    assert res["ok"] and res["improved"] is True
    assert "v2 improved" in (tmp_path / "flow-edge.md").read_text(encoding="utf-8")


def test_propose_skill_path_traversal_blocked(monkeypatch, tmp_path):
    import tools.skills as skills
    monkeypatch.setattr(skills, "SKILLS_DIR", tmp_path)
    res = asyncio.run(skills.propose_skill("../../etc/evil", "trying to escape the dir " * 5))
    # slug strips path separators -> stays confined inside SKILLS_DIR
    assert res["ok"]
    created = list(tmp_path.glob("*.md"))
    assert all(p.parent == tmp_path for p in created)
    assert not (tmp_path.parent / "etc").exists()


def test_propose_skill_rejects_thin_body(monkeypatch, tmp_path):
    import tools.skills as skills
    monkeypatch.setattr(skills, "SKILLS_DIR", tmp_path)
    assert asyncio.run(skills.propose_skill("x", "too short"))["ok"] is False
