from collections.abc import Callable, MutableMapping
import logging
from pathlib import Path
import sys
from typing import Any, Literal

from asgi_correlation_id import correlation_id
import structlog
from structlog.types import EventDict

# Default configuration - adjustable
DEFAULT_CONFIG: dict[str, Any] = {
    "console": {
        "enabled": True,
        "correlation_id_length": 8,
        "show_logger_name": False,
        "colorize_level": True,
    },
    "file": {
        "enabled": True,
        "format": "json",
        "path": "logs/app.log",
        "encoding": "utf-8",
        "mode": "a",
    },
    "external_loggers": {
        "propagate": [
            "uvicorn",
            "uvicorn.error",
            "uvicorn.access",
        ],
        "ignore": [
            "aiosqlite",
        ],
    },
}


# =========================
# Custom processors
# =========================
def add_cid(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Add correlation_id (full) and cid (short) into event_dict.
    Console will render only cid; file logs keep full correlation_id.
    """
    cid_value = correlation_id.get()
    if cid_value:
        event_dict["correlation_id"] = cid_value
        event_dict["cid"] = cid_value[: DEFAULT_CONFIG["console"]["correlation_id_length"]]
    else:
        event_dict["cid"] = ""
    return event_dict


# ANSI color codes for log levels
_LEVEL_COLORS = {
    "DEBUG": "\033[36m",  # cyan
    "INFO": "\033[32m",  # green
    "WARNING": "\033[33m",  # yellow
    "ERROR": "\033[31m",  # red
    "CRITICAL": "\033[35m",  # magenta
}
_RESET = "\033[0m"


def _trim_iso_to_ms(ts: str) -> str:
    """Trim an ISO8601 timestamp to HH:MM:SS.mmm. Accepts trailing 'Z' or offset."""
    if not ts or len(ts) < 20:
        return ts
    # for UTC 'Z' suffix, e.g. 2023-10-05T14:48:00.123Z
    if ts.endswith("Z"):
        return ts[11:-4]

    # for local time with offset, e.g. 2023-10-05T14:48:00.123456
    return ts[8:-3].replace("T", " ", 1)


def console_renderer() -> Callable[[Any, str, MutableMapping[str, Any]], str]:
    """
    Custom console renderer that places [cid] after log level,
    trims timestamp to milliseconds, colors log level if enabled,
    and hides correlation_id from the end of the line.
    NOTE: This renderer expects a single 'timestamp' inserted by TimeStamper.
    """
    return _render


def _render(logger: Any, method_name: str, event_dict: EventDict) -> str:
    ts = event_dict.pop("timestamp", None)
    level = event_dict.pop("level", "info").upper()
    logger_name = event_dict.pop("logger", None)
    cid = event_dict.pop("cid", "")
    msg = event_dict.pop("event", "")

    parts: list[str] = []
    if ts:
        parts.append(_trim_iso_to_ms(ts))

    # build colored level token
    lvl_text = f"{level:<8}"
    if DEFAULT_CONFIG["console"]["colorize_level"]:
        color = _LEVEL_COLORS.get(level, "")
        if color:
            lvl_token = f"{color}[{lvl_text}]{_RESET}"
        else:
            lvl_token = f"[{lvl_text}]"
    else:
        lvl_token = f"[{lvl_text}]"
    parts.append(lvl_token)

    # cid token
    if len(cid) > 0:
        parts.append(f"[{cid}]")

    # optional logger name
    if DEFAULT_CONFIG["console"]["show_logger_name"] and logger_name:
        parts.append(f"[{logger_name}]")

    parts.append(msg)
    return " ".join(parts)


# =========================
# Logger setup
# =========================
def _merge_dict(dst: dict[str, Any], src: dict[str, Any] | None) -> dict[str, Any]:
    out = {**dst}
    for k, v in (src or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_dict(out[k], v)
        else:
            out[k] = v
    return out


def setup_logger(
    is_debug: bool = False,
    log_level: str | None = None,
    log_format: Literal["json", "console"] = "json",
    log_file: str | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """Configure structlog + stdlib logging with consistent console/file output.

    Function signature is preserved for compatibility.
    """
    cfg = _merge_dict(DEFAULT_CONFIG, config or {})

    level = logging.DEBUG if is_debug else logging.INFO
    if log_level:
        level = logging.getLevelName(log_level.upper())

    # Root logger cleanup
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    # Shared pre-chain (no renderer!)
    pre_chain: list[Callable[[Any, str, MutableMapping[str, Any]], EventDict]] = [
        add_cid,
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Configure structlog: send events to stdlib via wrap_for_formatter.
    structlog.configure(
        processors=[*pre_chain, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # --- Console handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    if log_format == "console":
        console_formatter = structlog.stdlib.ProcessorFormatter(
            processor=console_renderer(),  # final renderer
            foreign_pre_chain=pre_chain,  # for non-structlog loggers
        )
    else:  # json to console (rare, but supported)
        console_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=pre_chain,
        )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # --- File handler ---
    if cfg["file"]["enabled"]:
        log_path = Path(log_file or cfg["file"]["path"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, mode=cfg["file"]["mode"], encoding=cfg["file"]["encoding"])
        file_handler.setLevel(level)
        file_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=pre_chain,
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Make external loggers flow into root
    for name in cfg["external_loggers"]["propagate"]:
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
        logging.getLogger(name).setLevel(level)

    # Disable noisy loggers
    for name in cfg["external_loggers"]["ignore"]:
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = False
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """External interface to get a structlog logger."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
