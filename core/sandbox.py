"""OS-level sandbox for model-authored code. On macOS we wrap execution in
`sandbox-exec` (seatbelt): the process may only WRITE inside an explicit
allow-list of directories AND may not READ the user's secrets (`.env`, SSH/AWS/
GCP/GPG credentials), so agent code cannot modify the project source, delete
files, change the system, or read and exfiltrate keys.

If sandbox-exec is unavailable (e.g. Linux/Windows), callers fall back to a
static guard and, by default, REFUSE to run (fail closed). See
`tools/code_runner.py`. (For Linux, bubblewrap/firejail would be the equivalent;
left as a future adapter.)
"""

from __future__ import annotations

import os
import shutil

_HOME = os.path.expanduser("~")


def available() -> bool:
    return shutil.which("sandbox-exec") is not None


def build_profile(write_dirs: list[str]) -> str:
    allows = "\n".join(f'  (subpath "{d}")' for d in write_dirs)
    return (
        "(version 1)\n"
        "(allow default)\n"            # exec allowed by default...
        # ...but deny reading the user's secrets so agent code cannot exfiltrate them:
        "(deny file-read*\n"
        f'  (subpath "{_HOME}/.ssh")\n'
        f'  (subpath "{_HOME}/.aws")\n'
        f'  (subpath "{_HOME}/.gnupg")\n'
        f'  (subpath "{_HOME}/.config/gcloud")\n'
        '  (regex #"/\\.env($|\\.)")\n'
        '  (regex #"\\.pem$")\n'
        '  (regex #"\\.key$"))\n'
        "(deny file-write*)\n"          # no writes...
        "(allow file-write*\n"          # ...except inside these dirs:
        f"{allows}\n"
        '  (subpath "/private/tmp")\n'
        '  (subpath "/private/var/folders")\n'
        '  (subpath "/tmp")\n'
        '  (literal "/dev/null")\n'
        '  (literal "/dev/stdout")\n'
        '  (literal "/dev/stderr")\n'
        '  (literal "/dev/urandom"))\n'
        "(allow network*)\n"
    )


def wrap_cmd(python_exe: str, script_path: str, write_dirs: list[str]) -> list[str] | None:
    """Return a sandbox-exec-wrapped command, or None if sandboxing isn't available."""
    if not available():
        return None
    return ["sandbox-exec", "-p", build_profile(write_dirs), python_exe, script_path]


# Defense-in-depth: refuse code with obviously destructive / escape / exfiltration
# patterns even before the OS sandbox runs it. Matching is case-insensitive (the
# code is lower-cased first) so uppercase evasion (`import SUBPROCESS`) is caught.
_BANNED = (
    # destructive / process / fs
    "shutil.rmtree", "os.remove", "os.unlink", "os.rmdir", "os.system",
    "subprocess", "pty.spawn", "ctypes", "os.kill", "sys.exit(", "shutil.move",
    ".unlink",
    # dynamic-import / introspection escapes
    "__import__", "importlib", "getattr(", "builtins", "eval(", "exec(",
    "globals(", "compile(", "marshal", "pickle",
    # network / exfiltration
    "socket", "requests", "httpx", "urllib", "ftplib", "smtplib",
    # sensitive paths (lower-cased)
    "/users/", "/home/", "/root/", "/etc/", "/.ssh", "/.aws", "/.gnupg",
)


def static_guard(code: str) -> str | None:
    """Return a reason string if the code looks dangerous, else None."""
    low = code.lower()
    for pat in _BANNED:
        if pat in low:
            return f"blocked by static guard: contains '{pat}'"
    return None
