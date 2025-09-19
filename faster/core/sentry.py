"""
Sentry integration for error tracking and performance monitoring.
"""

import logging
from typing import Any

from fastapi import Request
from sentry_sdk import (
    capture_exception,
    capture_message,
    get_client,
    init,
    set_context,
    set_tag,
    set_user,
)
from sentry_sdk.api import is_initialized
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.types import Event

from .config import Settings
from .logger import get_logger
from .plugins import BasePlugin

logger = get_logger(__name__)


class SentryManager(BasePlugin):
    def __init__(self) -> None:
        self.dsn: str | None = None
        self.trace_sample_rate: float = 0.1
        self.profiles_sample_rate: float = 0.1
        self.environment: str = "development"
        self.timeout: int = 10
        self.retries: int = 3
        self.shutdown_timeout: int = 5
        self.is_ready: bool = False


    def before_send(self, event: Event, hint: dict[str, Any]) -> Event | None:
        """Filter and modify events before sending to Sentry."""
        # Filter out health check transactions
        if event.get("transaction") == "/health":
            return None

        # Filter out Sentry SDK internal errors to prevent error loops
        if event.get("logger") == "sentry_sdk.errors":
            return None

        # Filter out network-related errors that are likely transient
        exception = event.get("exception")
        if exception and exception.get("values"):
            for exc_value in exception["values"]:
                exc_type = exc_value.get("type", "")
                exc_value_str = exc_value.get("value", "")

                # Skip common network errors that are transient
                if any(error_type in exc_type for error_type in [
                    "RemoteDisconnected", "ProtocolError", "ConnectionError",
                    "TimeoutError", "ConnectTimeout", "ReadTimeout"
                ]):
                    logger.debug(f"Filtered out transient network error: {exc_type}")
                    return None

                # Skip Sentry transport errors to prevent infinite loops
                if "sentry" in exc_value_str.lower() and any(keyword in exc_value_str.lower() for keyword in [
                    "transport", "connection", "remote end closed"
                ]):
                    logger.debug(f"Filtered out Sentry transport error: {exc_value_str}")
                    return None

        return event

    # -----------------------------
    # Plugin interface implementation
    # -----------------------------
    async def setup(self, settings: Settings) -> bool:
        """Set up Sentry SDK from settings."""
        self.dsn = settings.sentry_dsn
        self.trace_sample_rate = settings.sentry_trace_sample_rate
        self.profiles_sample_rate = settings.sentry_profiles_sample_rate
        self.environment = settings.environment
        self.timeout = settings.sentry_timeout
        self.retries = settings.sentry_retries
        self.shutdown_timeout = settings.sentry_shutdown_timeout

        if not self.dsn:
            logger.info("Sentry DSN not configured, skipping Sentry setup")
            self.is_ready = True
            return True

        try:
            _ = init(
                dsn=self.dsn,
                integrations=[
                    FastApiIntegration(failed_request_status_codes={400, *range(500, 600)}),
                    SqlalchemyIntegration(),
                    RedisIntegration(),
                    LoggingIntegration(
                        level=logging.INFO,
                        event_level=logging.ERROR
                    ),
                ],
                traces_sample_rate=self.trace_sample_rate,
                profiles_sample_rate=self.profiles_sample_rate,
                environment=self.environment,
                debug=self.environment == "development",
                before_send=self.before_send,
                send_default_pii=True,
                # Additional transport options
                shutdown_timeout=self.shutdown_timeout,  # Configurable shutdown timeout
                max_breadcrumbs=50,  # Limit breadcrumbs to reduce payload size
                attach_stacktrace=True,
                # Disable auto session tracking to reduce network calls
                auto_session_tracking=False,
            )
            logger.info("Sentry initialized")
            self.is_ready = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Sentry: {e}")
            self.is_ready = False
            return False

    async def teardown(self) -> bool:
        """Ensure all Sentry events are sent before shutdown."""
        try:
            client = get_client()
            if client and is_initialized():
                # Flush any pending events with configurable timeout
                client.flush(timeout=max(1.0, self.shutdown_timeout - 2.0))
                client.close(timeout=2.0)
                logger.info("Sentry client closed gracefully")
            else:
                logger.debug("Sentry client not initialized or already closed")
            self.is_ready = False
            return True
        except Exception as e:
            # Don't let Sentry teardown errors crash the application shutdown
            logger.warning(f"Non-critical error during Sentry client shutdown: {e}")
            self.is_ready = False
            return True  # Return True to not block application shutdown

    async def check_health(self) -> dict[str, Any]:
        """Check if Sentry is configured and initialized."""
        if not self.is_ready:
            return {
                "status": False,
                "configured": bool(self.dsn),
                "initialized": False,
                "reason": "Plugin not ready",
            }
        try:
            set_tag("health_check", True)
            return {
                "status": True,
                "configured": bool(self.dsn),
                "initialized": is_initialized(),
            }
        except Exception as e:
            logger.error(f"Sentry health check failed: {e}")
            return {
                "status": False,
                "configured": bool(self.dsn),
                "initialized": False,
                "error": str(e),
            }


async def capture_it(obj: Exception | str) -> None:
    """Helper function to capture an exception or message with Sentry safely."""
    try:
        # Only attempt to send to Sentry if it's properly initialized
        if not is_initialized():
            logger.debug("Sentry not initialized, skipping capture")
            return

        if isinstance(obj, Exception):
            logger.error("[exception] %s", obj, exc_info=True)
            _ = capture_exception(obj)
        elif isinstance(obj, str):
            logger.error(obj)
            _ = capture_message(obj)
        # elif isinstance(obj, Event):
        #     capture_event(obj)
    except Exception as e:
        # Don't let Sentry errors crash the application
        # Just log the issue and continue
        logger.warning(f"Failed to send event to Sentry (non-critical): {e}")

        # If this is a Sentry transport error, we might want to temporarily disable Sentry
        if any(keyword in str(e).lower() for keyword in [
            "remote end closed", "connection aborted", "protocol error", "timeout"
        ]):
            logger.info("Detected Sentry transport issue, events will be logged locally only")


async def add_sentry_context(request: Request, user_id: str = "") -> None:
    """DI helper function to Add relevant context to Sentry events."""
    if user_id:
        set_user({"id": user_id})

    set_tag("endpoint", request.url.path)
    set_context(
        "request_info",
        {
            "x-request-id": request.headers.get("x-request-id"),
            "method": request.method,
            "user_agent": request.headers.get("user-agent"),
            "ip": request.client.host if request.client else None,
        },
    )
