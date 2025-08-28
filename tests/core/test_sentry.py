from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import Request
import pytest

from faster.core.sentry import (
    SentryManager,
    add_sentry_context,
    capture_it,
)


@pytest.fixture(autouse=True)
def reset_sentry_manager_singleton() -> None:
    """
    Fixture to reset the SentryManager singleton before each test.
    This ensures test isolation.
    """
    SentryManager._instance = None


@pytest.fixture
def mock_sentry_init() -> MagicMock:
    """Fixture to mock sentry_sdk.init."""
    with patch("faster.core.sentry.init") as mock:
        yield mock


@pytest.fixture
def mock_sentry_client() -> MagicMock:
    """Fixture to mock the Sentry client and its close method."""
    with patch("faster.core.sentry.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_sentry_capture_exception() -> Generator[MagicMock, None, None]:
    """Fixture to mock sentry_sdk.capture_exception."""
    with patch("faster.core.sentry.capture_exception") as mock:
        yield mock


@pytest.fixture
def mock_sentry_capture_message() -> MagicMock:
    """Fixture to mock sentry_sdk.capture_message."""
    with patch("faster.core.sentry.capture_message") as mock:
        yield mock


@pytest.fixture
def mock_sentry_context_setters() -> dict[str, MagicMock]:
    """Fixture to mock all Sentry context-setting functions."""
    with (
        patch("faster.core.sentry.set_user") as mock_set_user,
        patch("faster.core.sentry.set_tag") as mock_set_tag,
        patch("faster.core.sentry.set_context") as mock_set_context,
    ):
        yield {
            "set_user": mock_set_user,
            "set_tag": mock_set_tag,
            "set_context": mock_set_context,
        }


# =================================
# SentryManager Tests
# =================================


def test_sentry_manager_is_singleton():
    """Arrange: N/A, Act: Get two instances, Assert: They are the same object."""
    instance1 = SentryManager.get_instance()
    instance2 = SentryManager.get_instance()
    assert instance1 is instance2


@pytest.mark.asyncio
async def test_setup_initializes_sentry_when_dsn_is_provided(mock_sentry_init: MagicMock):
    """
    Arrange: DSN and other settings.
    Act: Call setup.
    Assert: sentry_sdk.init is called with the correct parameters.
    """
    # Arrange
    sentry_manager = SentryManager.get_instance()
    dsn = "https://test_dsn@sentry.io/12345"
    trace_sample_rate = 0.5
    profiles_sample_rate = 0.5
    environment = "production"

    # Act
    await sentry_manager.setup(
        dsn=dsn,
        trace_sample_rate=trace_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        environment=environment,
    )

    # Assert
    mock_sentry_init.assert_called_once()
    args, kwargs = mock_sentry_init.call_args
    assert kwargs["dsn"] == dsn
    assert kwargs["traces_sample_rate"] == trace_sample_rate
    assert kwargs["profiles_sample_rate"] == profiles_sample_rate
    assert kwargs["environment"] == environment
    assert "integrations" in kwargs
    assert kwargs["before_send"] == sentry_manager.before_send


@pytest.mark.asyncio
@pytest.mark.parametrize("dsn", [None, ""])
async def test_setup_does_not_initialize_sentry_when_dsn_is_missing(dsn: str | None, mock_sentry_init: MagicMock):
    """
    Arrange: An invalid DSN (None or empty).
    Act: Call setup.
    Assert: sentry_sdk.init is not called.
    """
    # Arrange
    sentry_manager = SentryManager.get_instance()

    # Act
    await sentry_manager.setup(dsn=dsn)

    # Assert
    mock_sentry_init.assert_not_called()


def test_before_send_filters_health_check_events():
    """

    Arrange: A Sentry event for a /health transaction.
    Act: Call before_send.
    Assert: The event is rejected (returns None).
    """
    # Arrange
    sentry_manager = SentryManager.get_instance()
    health_event = {"transaction": "/health"}
    hint = {}

    # Act
    result = sentry_manager.before_send(health_event, hint)

    # Assert
    assert result is None


def test_before_send_allows_other_events():
    """
    Arrange: A Sentry event for a normal transaction.
    Act: Call before_send.
    Assert: The event is passed through (returns the event).
    """
    # Arrange
    sentry_manager = SentryManager.get_instance()
    other_event = {"transaction": "/api/users"}
    hint = {}

    # Act
    result = sentry_manager.before_send(other_event, hint)

    # Assert
    assert result is other_event


@pytest.mark.asyncio
async def test_close_flushes_sentry_client(mock_sentry_client: MagicMock):
    """
    Arrange: A mocked Sentry client.
    Act: Call close.
    Assert: The client's close method is called.
    """
    # Arrange
    sentry_manager = SentryManager.get_instance()

    # Act
    await sentry_manager.close()

    # Assert
    mock_sentry_client.close.assert_called_once_with(timeout=2.0)


@pytest.mark.asyncio
async def test_check_health_when_configured():
    """
    Arrange: Setup SentryManager with a DSN.
    Act: Call check_health.
    Assert: Returns configured status as True.
    """
    # Arrange
    sentry_manager = SentryManager.get_instance()
    sentry_manager.dsn = "https://fake-dsn"

    # Act
    health = await sentry_manager.check_health()

    # Assert
    assert health == {"status": True, "configured": True, "initialized": True}


@pytest.mark.asyncio
async def test_check_health_when_not_configured():
    """
    Arrange: SentryManager is not configured with a DSN.
    Act: Call check_health.
    Assert: Returns configured status as False.
    """
    # Arrange
    sentry_manager = SentryManager.get_instance()
    sentry_manager.dsn = None

    # Act
    health = await sentry_manager.check_health()

    # Assert
    assert health == {"status": True, "configured": False, "initialized": True}


# =================================
# Helper Functions Tests
# =================================


@pytest.mark.asyncio
async def test_capture_it_with_exception(mock_sentry_capture_exception: MagicMock):
    """
    Arrange: An exception object.
    Act: Call capture_it.
    Assert: sentry_sdk.capture_exception is called with the exception.
    """
    # Arrange
    error = ValueError("This is a test error")

    # Act
    await capture_it(error)

    # Assert
    mock_sentry_capture_exception.assert_called_once_with(error)


@pytest.mark.asyncio
async def test_capture_it_with_message(mock_sentry_capture_message: MagicMock):
    """
    Arrange: A string message.
    Act: Call capture_it.
    Assert: sentry_sdk.capture_message is called with the message.
    """
    # Arrange
    message = "This is a test message"

    # Act
    await capture_it(message)

    # Assert
    mock_sentry_capture_message.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_add_sentry_context(mock_sentry_context_setters: dict[str, MagicMock]):
    """
    Arrange: A mock FastAPI request and user ID.
    Act: Call add_sentry_context.
    Assert: Sentry context setters are called with the correct data.
    """
    # Arrange
    mock_request = AsyncMock(spec=Request)
    mock_request.url.path = "/test/path"
    mock_request.headers = {
        "x-request-id": "test-request-id",
        "user-agent": "pytest-client",
    }
    mock_request.method = "GET"
    mock_request.client = AsyncMock()
    mock_request.client.host = "127.0.0.1"
    user_id = "user-123"

    # Act
    await add_sentry_context(mock_request, user_id=user_id)

    # Assert
    mock_sentry_context_setters["set_user"].assert_called_once_with({"id": user_id})
    mock_sentry_context_setters["set_tag"].assert_called_once_with("endpoint", "/test/path")
    mock_sentry_context_setters["set_context"].assert_called_once_with(
        "request_info",
        {
            "x-request-id": "test-request-id",
            "method": "GET",
            "user_agent": "pytest-client",
            "ip": "127.0.0.1",
        },
    )
