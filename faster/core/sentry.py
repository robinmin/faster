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

from .logger import get_logger

logger = get_logger(__name__)


class SentryManager:
    _instance = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "SentryManager":
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        self.dsn: str | None = None
        self.trace_sample_rate: float = 0.1
        self.profiles_sample_rate: float = 0.1
        self.environment: str = "development"

    @classmethod
    def get_instance(cls) -> "SentryManager":
        if cls._instance is None:
            cls._instance = SentryManager()
        return cls._instance

    async def setup(
        self,
        dsn: str | None = None,
        trace_sample_rate: float = 0.1,
        profiles_sample_rate: float = 0.1,
        environment: str = "development",
    ) -> None:
        """Set up Sentry SDK."""
        self.dsn = dsn
        self.trace_sample_rate = trace_sample_rate
        self.profiles_sample_rate = profiles_sample_rate
        self.environment = environment

        if not self.dsn:
            return

        init(
            dsn=self.dsn,
            integrations=[
                FastApiIntegration(failed_request_status_codes={400, *range(500, 600)}),
                # StarletteIntegration(transaction_style="endpoint"),
                # SentryAsgiMiddleware(),
                SqlalchemyIntegration(),
                RedisIntegration(),
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            ],
            traces_sample_rate=self.trace_sample_rate,
            profiles_sample_rate=self.profiles_sample_rate,
            environment=self.environment,
            debug=self.environment == "development",
            before_send=self.before_send,
            # Add data like request headers and IP for users,
            # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
            send_default_pii=True,
        )
        logger.info("Sentry initialized")

    def before_send(self, event: Event, hint: dict[str, Any]) -> Event | None:
        """Filter and modify events before sending to Sentry."""
        if event.get("transaction") == "/health":
            return None
        return event

    async def close(self) -> None:
        """Ensure all Sentry events are sent before shutdown."""
        client = get_client()
        if client:
            client.close(timeout=2.0)
        logger.info("Sentry closed")

    async def check_health(self) -> dict[str, Any]:
        """Check if Sentry is configured."""
        set_tag("health_check", True)
        return {
            "status": True,
            "configured": bool(self.dsn),
            "initialized": is_initialized(),
        }


async def capture_it(obj: Exception | str) -> None:
    """Helper function to capture an exception or message with Sentry."""
    if isinstance(obj, Exception):
        logger.error("[exception] %s", obj, exc_info=True)
        capture_exception(obj)
    elif isinstance(obj, str):
        logger.error(obj)
        capture_message(obj)
    # elif isinstance(obj, Event):
    #     capture_event(obj)


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
