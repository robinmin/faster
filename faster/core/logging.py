# logging_utils.py
from collections.abc import MutableMapping
from datetime import datetime
import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor


def human_friendly_timestamp(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Add a human-friendly timestamp with milliseconds (HH:MM:SS.mmm)"""
    event_dict["timestamp"] = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # remove last 3 digits
    return event_dict


def setup_logger(
    is_debug: bool,
    log_level: str | None = None,
    log_format: str = "json",
    log_file: str | None = None,
    propagate_loggers: list[str] | None = None,
) -> None:
    """
    Setup logging with structlog for FastAPI applications.

    Args:
        is_debug: Enable debug level logging
        log_level: Optional log level ("INFO", "DEBUG", etc.)
        log_format: "json" or "console" for log file format
        log_file: Optional file path for logging
        propagate_loggers: List of logger names to propagate to root logger
    """
    # 1. Resolve log level
    level = logging.DEBUG if is_debug else logging.INFO
    if log_level:
        level = getattr(logging, log_level.upper(), level)

    # 2. Shared processors for both console and file
    shared_processors: list[Processor] = [
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # -----------------------------
    # Console Handler (human-friendly)
    # -----------------------------
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
            foreign_pre_chain=[
                human_friendly_timestamp,
                *shared_processors,
            ],
        )
    )

    handlers: list[logging.Handler] = [console_handler]

    # -----------------------------
    # File Handler (JSON or plain text)
    # -----------------------------
    if log_file:
        file_renderer: Processor
        if log_format.lower() == "json":
            file_renderer = structlog.processors.JSONRenderer()
        else:
            file_renderer = structlog.dev.ConsoleRenderer(colors=False)

        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processor=file_renderer,
                foreign_pre_chain=[
                    (
                        structlog.processors.TimeStamper(fmt="iso", utc=True)
                        if log_format.lower() == "json"
                        else human_friendly_timestamp
                    ),
                    *shared_processors,
                ],
            )
        )
        handlers.append(file_handler)

    # -----------------------------
    # Configure root logging
    # -----------------------------
    logging.basicConfig(level=level, handlers=handlers, format="%(message)s")

    # -----------------------------
    # Configure structlog
    # -----------------------------
    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # -----------------------------
    # Propagate other loggers
    # -----------------------------
    if propagate_loggers:
        for logger_name in propagate_loggers:
            log = logging.getLogger(logger_name)
            log.handlers = []
            log.propagate = True
