import asyncio
from unittest.mock import patch

import pytest

from faster.core.config import Settings
from faster.core.redis import RedisManager


def pytest_configure(config):
    """
    Initializes the Redis manager with a fake provider before tests are collected.
    """
    settings = Settings(redis_provider="fake")
    asyncio.run(RedisManager.get_instance().setup(settings))


@pytest.fixture(autouse=True)
def disable_sentry_for_non_sentry_tests(request):
    """
    Auto-used fixture to disable Sentry during non-Sentry tests to prevent logging errors
    when Sentry tries to send events after test completion.
    """
    # Only disable Sentry for non-Sentry tests
    if "sentry" not in request.module.__name__:
        with (
            patch("faster.core.sentry.SentryManager.setup", return_value=True),
            patch("faster.core.sentry.init") as mock_init,
            patch("faster.core.sentry.capture_exception") as mock_capture_exception,
            patch("faster.core.sentry.capture_message") as mock_capture_message,
            patch("faster.core.sentry.is_initialized", return_value=False),
        ):
            mock_init.return_value = None
            mock_capture_exception.return_value = None
            mock_capture_message.return_value = None
            yield
    else:
        # For Sentry tests, don't mock anything
        yield
