"""Tool plugin auto-discovery: dropping a file in tools/plugins/ adds a tool."""

from __future__ import annotations

from pathlib import Path

from core.blackboard import Blackboard
from tools.data_tools import build_data_registry

_PLUGIN = '''
async def zz_unit_tool(**params):
    return {"ok": True, "echo": params}

def register(reg):
    reg.register("zz_unit_tool", zz_unit_tool)
'''


def test_plugin_autoloaded(tmp_path) -> None:
    plugins_dir = Path(__file__).resolve().parent.parent / "tools" / "plugins"
    f = plugins_dir / "zz_unit_test_plugin.py"
    f.write_text(_PLUGIN, encoding="utf-8")
    try:
        reg = build_data_registry(Blackboard(path=tmp_path / "t.db"))
        assert "zz_unit_tool" in reg.available()
    finally:
        f.unlink(missing_ok=True)
        # also remove any compiled cache
        for p in plugins_dir.glob("__pycache__/zz_unit_test_plugin*"):
            p.unlink(missing_ok=True)
