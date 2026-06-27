"""Sandboxed Python execution so agents can write and run THEIR OWN analyses —
the basis for self-taught quant research. A script is written to a sandbox dir and
run as a subprocess in the project venv with a hard timeout; stdout/stderr are
captured and truncated.

SECURITY NOTE: this executes model-authored code. It is OFF by default and gated
by `settings.agents.allow_code_execution`. When enabled on macOS it runs under
`sandbox-exec` (writes confined to the sandbox dir; reads of `.env`/SSH/AWS/GCP
secrets denied). On Linux/Windows there is no OS sandbox, so it FAILS CLOSED
(refuses to run) unless `LOOPFUND_ALLOW_UNSANDBOXED=1` is set explicitly. A static
guard rejects destructive / import-escape / network patterns before running. It
does NOT use a shell (no string injection) and enforces a timeout. Review saved
scripts under quant/scripts/. Do not enable on a machine with secrets you would
not hand to the model.
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from core.config import ROOT, settings
from core.logging import get_logger

log = get_logger("code_runner")

SANDBOX = ROOT / "quant" / "scripts" / "sandbox"
_MAX_OUT = 8000


def code_execution_allowed() -> bool:
    # OFF by default — opt in via settings.agents.allow_code_execution.
    return bool(settings().get("agents", {}).get("allow_code_execution", False))


async def run_python(code: str, script_name: str = "script", timeout_s: int = 60) -> dict:
    """Write `code` to the sandbox and execute it. Returns stdout/stderr/returncode."""
    if not code_execution_allowed():
        return {"ok": False, "error": "code execution disabled in settings", "stdout": "", "stderr": ""}

    # defense-in-depth: refuse obviously dangerous code before it ever runs
    from core import sandbox as sbx

    guard = sbx.static_guard(code)
    if guard:
        log.warning("run_python_blocked", reason=guard)
        return {"ok": False, "error": guard, "stdout": "", "stderr": guard, "blocked": True}

    SANDBOX.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in script_name)[:60] or "script"
    # Unique suffix so concurrent/repeated runs never overwrite each other's script.
    path = SANDBOX / f"{safe}_{uuid.uuid4().hex[:8]}.py"
    path.write_text(code, encoding="utf-8")

    # OS sandbox: confine writes to the sandbox dir; reads + network allowed
    cmd = sbx.wrap_cmd(sys.executable, str(path), [str(SANDBOX)])
    sandboxed = cmd is not None
    if not sandboxed:
        # FAIL CLOSED: no OS sandbox available (e.g. Linux/ECS, where sandbox-exec
        # doesn't exist). Running model-authored Python with only a static guard is an
        # RCE risk, so refuse by default. Set LOOPFUND_ALLOW_UNSANDBOXED=1 to opt in
        # knowingly (only on a machine where that is acceptable).
        import os
        if os.environ.get("LOOPFUND_ALLOW_UNSANDBOXED") != "1":
            log.warning("run_python_refused_no_sandbox",
                        note="OS sandbox unavailable; refusing to run model code unsandboxed")
            return {"ok": False, "error": "no OS sandbox available; code execution refused "
                    "(set LOOPFUND_ALLOW_UNSANDBOXED=1 to override on a safe machine)",
                    "stdout": "", "stderr": "", "blocked": True}
        cmd = [sys.executable, str(path)]
        log.warning("run_python_unsandboxed", note="explicit override; static guard only")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(SANDBOX),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
            timed_out = False
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            out, err = b"", b"timeout"
            timed_out = True
    except Exception as exc:
        log.error("run_python_failed", error=str(exc))
        return {"ok": False, "error": str(exc), "stdout": "", "stderr": "", "script": str(path)}

    stdout = out.decode("utf-8", "replace")[:_MAX_OUT]
    stderr = err.decode("utf-8", "replace")[:_MAX_OUT]
    rc = proc.returncode
    log.info("run_python", name=safe, rc=rc, timed_out=timed_out, sandboxed=sandboxed)
    return {"ok": (rc == 0 and not timed_out), "returncode": rc, "timed_out": timed_out,
            "stdout": stdout, "stderr": stderr, "script": str(path), "sandboxed": sandboxed}
