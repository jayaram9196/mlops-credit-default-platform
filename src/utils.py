"""Shared utilities: config loading, structured logging, project paths."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import structlog
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARAMS_PATH = PROJECT_ROOT / "params.yaml"


def load_params(path: Path | str = PARAMS_PATH) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"params file not found: {path}")
    with path.open() as fh:
        return yaml.safe_load(fh)


def configure_logging(level: str = "INFO", json_logs: bool | None = None) -> None:
    if json_logs is None:
        json_logs = not sys.stderr.isatty()

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    processors.append(
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def project_path(*parts: str | Path) -> Path:
    return PROJECT_ROOT.joinpath(*[str(p) for p in parts])


def ensure_dir(path: Path | str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
