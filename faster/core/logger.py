from collections.abc import Callable, MutableMapping
import logging
from pathlib import Path
import sys
from typing import Any, Literal

from asgi_correlation_id import correlation_id
import structlog
from structlog.types import EventDict

from .config import get_default_logger_config

###############################################################################

# Default configuration - adjustable
_default_config: dict[str, Any] = get_default_logger_config()


# Custom processors
def add_cid(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Add correlation_id (full) and cid (short) into event_dict.
    Console will render only cid; file logs keep full correlation_id.
    """
    cid_value = correlation_id.get()
    if cid_value:
        event_dict["correlation_id"] = cid_value
        event_dict["cid"] = cid_value[: _default_config["console"]["correlation_id_length"]]
    else:
        event_dict["cid"] = ""
    return event_dict


# ANSI color codes for log levels
_LEVEL_COLORS = {
    ## upper case keys
    "DEBUG": "\033[32m",  # green
    "INFO": "\033[34m",  # blue
    "WARNING": "\033[33m",  # yellow
    "ERROR": "\033[31m",  # red
    "CRITICAL": "\033[35m",  # magenta
    ## lower case keys
    "debug": "\033[32m",  # green
    "info": "\033[34m",  # blue
    "warning": "\033[33m",  # yellow
    "error": "\033[31m",  # red
    "critical": "\033[35m",  # magenta
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
    ts = event_dict.get("timestamp")
    level = str(event_dict.get("level", "info"))
    logger_name = event_dict.get("logger")
    cid = event_dict.get("cid", "")
    msg = str(event_dict.get("event", ""))

    parts: list[str] = []
    if ts:
        parts.append(_trim_iso_to_ms(str(ts)))

    # build colored level token
    lvl_text = f"{level:<8}"
    if _default_config["console"]["colorize_level"]:
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
    if _default_config["console"]["show_logger_name"] and logger_name:
        parts.append(f"[{logger_name}]")

    parts.append(msg)
    return " ".join(parts)


def file_renderer() -> Callable[[Any, str, MutableMapping[str, Any]], str]:
    """
    Custom file renderer for plain text logs without colors.
    """
    return _render_file


def _render_file(logger: Any, method_name: str, event_dict: EventDict) -> str:
    ts = event_dict.get("timestamp", "")
    level = str(event_dict.get("level", ""))
    cid = event_dict.get("correlation_id", "")
    msg = event_dict.get("event", "")
    logger_name = event_dict.get("logger")

    parts: list[str] = []
    if ts:
        parts.append(str(ts))

    lvl_text = f"{level:<8}"
    lvl_token = f"[{lvl_text}]"
    parts.append(lvl_token)

    if cid:
        parts.append(f"[{cid}]")

    if _default_config["console"]["show_logger_name"] and logger_name:
        parts.append(f"[{logger_name}]")

    parts.append(str(msg))

    # Render remaining keys, avoiding duplicates
    extra = {
        k: v
        for k, v in event_dict.items()
        if k not in ["timestamp", "level", "correlation_id", "event", "cid", "logger", "log_level", "logger_name"]
    }
    if extra:
        parts.append(str(extra))

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
    cfg = _merge_dict(_default_config, config or {})

    level = logging.DEBUG if is_debug else logging.INFO
    if log_level:
        level = logging.getLevelName(log_level)

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
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=console_renderer(),  # final renderer
        foreign_pre_chain=pre_chain,  # for non-structlog loggers
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # --- File handler ---
    if cfg["file"]["enabled"]:
        log_path = Path(log_file or cfg["file"]["path"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            log_path, mode=str(cfg["file"]["mode"]), encoding=str(cfg["file"]["encoding"])
        )
        file_handler.setLevel(level)

        file_processor: Any
        if log_format == "console":
            file_processor = file_renderer()
        else:  # json
            file_processor = structlog.processors.JSONRenderer()

        file_formatter: structlog.stdlib.ProcessorFormatter = structlog.stdlib.ProcessorFormatter(
            processor=file_processor,
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
