"""Configuration loading. YAML for settings, .env for secrets.

Secrets are read from environment only — never from the YAML files, never
hardcoded. Missing optional keys degrade gracefully (the relevant data source
is simply disabled).
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"

load_dotenv(ROOT / ".env")


def _load_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"missing config file: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache(maxsize=1)
def settings() -> dict[str, Any]:
    return _load_yaml("settings.yaml")


@lru_cache(maxsize=1)
def models_config() -> dict[str, Any]:
    return _load_yaml("models.yaml")


@lru_cache(maxsize=1)
def risk_limits() -> dict[str, Any]:
    return _load_yaml("risk_limits.yaml")


def reload() -> None:
    """Clear caches so edited YAML is picked up without a restart (Phase 7)."""
    settings.cache_clear()
    models_config.cache_clear()
    risk_limits.cache_clear()


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


_CONFIG_FILES = {"settings": "settings.yaml", "models": "models.yaml", "risk_limits": "risk_limits.yaml"}


# Keys that must never be changed through the API/config-patch path: flipping the
# trading mode, or redirecting where agent code/briefings load from, are privilege
# escalations if the dashboard is ever exposed beyond localhost.
_PROTECTED_PATCH_KEYS = {"mode", "dynamic_dir", "briefings_dir"}


def _reject_protected(patch: dict[str, Any]) -> None:
    for k, v in patch.items():
        if k in _PROTECTED_PATCH_KEYS:
            raise KeyError(f"'{k}' cannot be changed via the API")
        if isinstance(v, dict):
            _reject_protected(v)


def update_config(name: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge a patch into a config file, write it, and reload caches."""
    if name not in _CONFIG_FILES:
        raise KeyError(f"unknown config '{name}' (have: {list(_CONFIG_FILES)})")
    _reject_protected(patch)
    current = _load_yaml(_CONFIG_FILES[name])
    merged = _deep_merge(current, patch)
    path = CONFIG_DIR / _CONFIG_FILES[name]
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(merged, fh, sort_keys=False)
    reload()
    return merged


def env(key: str, default: str | None = None) -> str | None:
    """Read a secret/config value from the environment."""
    return os.environ.get(key, default)


_ENV_KEY_RE = re.compile(r"[A-Z][A-Z0-9_]{1,63}")


def persist_env(key: str, value: str) -> None:
    """Set an env var for this process AND persist it to .env (gitignored) so it
    survives a restart. Used by the dashboard's API-key input so a user can paste a
    key in the UI instead of editing files. Never logged.

    The key must match a strict UPPER_SNAKE pattern and the value is stripped of
    newlines/NULs so a crafted value cannot inject extra lines into .env."""
    if not _ENV_KEY_RE.fullmatch(key):
        raise ValueError(f"invalid env key: {key!r}")
    # Strip characters that would let a value spill into a new .env line.
    value = value.replace("\r", "").replace("\n", "").replace("\x00", "")
    os.environ[key] = value
    env_path = ROOT / ".env"
    lines: list[str] = []
    found = False
    if env_path.exists():
        for ln in env_path.read_text(encoding="utf-8").splitlines():
            if ln.split("=", 1)[0].strip() == key:
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(ln)
    if not found:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def data_dir() -> Path:
    d = ROOT / "data"
    d.mkdir(exist_ok=True)
    return d
