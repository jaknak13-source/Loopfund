"""Structured logging. Long output goes to files under logs/, not chat/stdout."""

from __future__ import annotations

import logging

import structlog

from core.config import ROOT, settings

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return

    cfg = settings().get("logging", {})
    level = getattr(logging, str(cfg.get("level", "INFO")).upper(), logging.INFO)
    log_dir = ROOT / cfg.get("dir", "logs")
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "system.log", encoding="utf-8"),
        ],
    )
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    setup_logging()
    return structlog.get_logger(name)
