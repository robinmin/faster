from collections.abc import Generator
import signal
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
import pytest
from starlette.routing import Route

from faster.core import bootstrap
from faster.core.config import Settings

# Individual tests are marked with @pytest.mark.asyncio as needed


@pytest.fixture
def mock_settings() -> Settings:
    """Fixture for mock settings."""
    return Settings(
        app_name="Test App",
        app_version="0.1.0",
        environment="development",
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost",
        jwt_secret_key="test-secret",
        auth_enabled=True,
        cors_enabled=True,
        gzip_enabled=True,
    )


@pytest.fixture
def mock_db_mgr() -> Generator[MagicMock, None, None]:
    """Fixture for mocking DatabaseManager.get_instance()."""
    mock_instance = MagicMock()
    mock_instance.setup = AsyncMock(return_value=True)
    mock_instance.teardown = AsyncMock(return_value=True)
    mock_instance.check_health = AsyncMock(return_value={"master": True})
    # Legacy methods for fallback compatibility
    mock_instance.initialize = AsyncMock(return_value=True)
    mock_instance.close = AsyncMock(return_value=True)

    with patch("faster.core.bootstrap.DatabaseManager.get_instance", return_value=mock_instance):
        yield mock_instance


@pytest.fixture
def mock_redis_mgr() -> Generator[MagicMock, None, None]:
    """Fixture for mocking RedisManager.get_instance()."""
    mock_instance = MagicMock()
    mock_instance.setup = AsyncMock(return_value=True)
    mock_instance.teardown = AsyncMock(return_value=True)
    mock_instance.check_health = AsyncMock(return_value={"ping": True})
    # Legacy methods for fallback compatibility
    mock_instance.initialize = AsyncMock(return_value=True)
    mock_instance.close = AsyncMock(return_value=True)

    with patch("faster.core.bootstrap.RedisManager.get_instance", return_value=mock_instance):
        yield mock_instance


@pytest.fixture
def mock_plugin_mgr() -> Generator[MagicMock, None, None]:
    """Fixture for mocking PluginManager.get_instance()."""
    mock_instance = MagicMock()
    mock_instance.setup = AsyncMock(return_value=True)
    mock_instance.teardown = AsyncMock(return_value=True)
    mock_instance.check_health = AsyncMock(
        return_value={
            "database": {"master": True},
            "redis": {"ping": True},
            "sentry": {"enabled": False},
        }
    )
    with patch("faster.core.bootstrap.PluginManager.get_instance", return_value=mock_instance):
        yield mock_instance


@pytest.fixture
def mock_auth_service() -> Generator[MagicMock, None, None]:
    """Fixture for mocking AuthService."""
    with patch("faster.core.bootstrap.AuthService", new_callable=MagicMock) as mock:
        yield mock


@pytest.mark.asyncio
async def test_default_startup_handler() -> None:
    assert await bootstrap.default_startup_handler() is True


@pytest.mark.asyncio
async def test_default_shutdown_handler() -> None:
    assert await bootstrap.default_shutdown_handler() is True


@pytest.mark.asyncio
async def test_setup_all(mock_settings: Settings, mock_plugin_mgr: MagicMock) -> None:
    app = FastAPI()
    app.state.plugin_mgr = mock_plugin_mgr
    await bootstrap._setup_all(app, mock_settings)

    mock_plugin_mgr.setup.assert_called_once_with(mock_settings)


@pytest.mark.asyncio
async def test_setup_all_no_db_url(mock_settings: Settings, mock_plugin_mgr: MagicMock) -> None:
    mock_settings.database_url = None
    app = FastAPI()
    app.state.plugin_mgr = mock_plugin_mgr
    await bootstrap._setup_all(app, mock_settings)

    mock_plugin_mgr.setup.assert_called_once_with(mock_settings)


@pytest.mark.asyncio
async def test_teardown_all(mock_plugin_mgr: MagicMock) -> None:
    app = FastAPI()
    app.state.plugin_mgr = mock_plugin_mgr
    await bootstrap._teardown_all(app)

    mock_plugin_mgr.teardown.assert_called_once()


def test_add_middlewares(mock_settings: Settings, mock_auth_service: MagicMock) -> None:
    app = FastAPI()
    bootstrap._add_middlewares(app, mock_settings)

    # Gzip, TrustedHost, Auth, CORS, CorrelationIdMiddleware
    assert len(app.user_middleware) == 6


def test_add_middlewares_disabled(mock_settings: Settings) -> None:
    mock_settings.auth_enabled = False
    mock_settings.cors_enabled = False
    mock_settings.gzip_enabled = False
    app = FastAPI()
    bootstrap._add_middlewares(app, mock_settings)

    # Only TrustedHost and CorrelationIdMiddleware
    assert len(app.user_middleware) == 3


@pytest.mark.asyncio
async def test_refresh_status(mock_settings: Settings, mock_plugin_mgr: MagicMock, caplog: Any) -> None:
    app = FastAPI()
    app.state.settings = mock_settings
    app.state.plugin_mgr = mock_plugin_mgr
    # Just verify the function runs without error
    await bootstrap.refresh_status(app, mock_settings, verbose=True)

    # Verify the mock was called
    mock_plugin_mgr.check_health.assert_called_once()


def test_create_app(mock_settings: Settings, mock_db_mgr: MagicMock, mock_redis_mgr: MagicMock) -> None:
    app = bootstrap.create_app(settings=mock_settings)
    assert isinstance(app, FastAPI)
    assert app.state.settings == mock_settings
    assert len(app.exception_handlers) > 2  # Check if handlers are added


def test_create_app_lifespan(mock_settings: Settings) -> None:
    startup_mock = AsyncMock(return_value=True)
    shutdown_mock = AsyncMock(return_value=True)

    app = bootstrap.create_app(
        settings=mock_settings,
        startup_handler=startup_mock,
        shutdown_handler=shutdown_mock,
    )

    with (
        patch("faster.core.bootstrap._setup_all") as setup_mock,
        patch("faster.core.bootstrap._teardown_all") as close_mock,
        patch("faster.core.bootstrap.refresh_status"),
    ):
        with TestClient(app):
            setup_mock.assert_called_once()
            startup_mock.assert_called_once()
        close_mock.assert_called_once()
        shutdown_mock.assert_called_once()


def test_create_app_lifespan_startup_fails(mock_settings: Settings) -> None:
    startup_mock = AsyncMock(return_value=False)
    startup_mock.__name__ = "startup_mock"
    app = bootstrap.create_app(settings=mock_settings, startup_handler=startup_mock)

    # Mock the logger to capture the critical log message
    with (
        patch("faster.core.bootstrap._setup_all"),
        patch("faster.core.bootstrap.refresh_status"),
        patch("faster.core.bootstrap.logger.critical") as mock_critical,
    ):
        with TestClient(app):
            pass  # Lifespan is triggered on context entry

        # Verify that the critical log was called with the expected message
        mock_critical.assert_called_once()
        call_args = mock_critical.call_args[0][0]
        assert "Application startup failed" in call_args
        assert "Startup handler startup_mock failed" in call_args

    startup_mock.assert_called_once()


def test_create_app_with_routers_and_middlewares(mock_settings: Settings) -> None:
    custom_router = APIRouter()

    @custom_router.get("/custom-route")
    async def my_custom_route() -> dict[str, str]:
        return {"message": "success"}

    class CustomMiddleware:
        def __init__(self, app: Any) -> None:
            self.app = app

        async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
            await self.app(scope, receive, send)

    app = bootstrap.create_app(
        settings=mock_settings,
        routers=[custom_router],
        middlewares=[CustomMiddleware],
    )

    # Gzip, TrustedHost, Auth, CORS, Custom, CorrelationIdMiddleware, SentryAsgiMiddleware
    assert len(app.user_middleware) == 7

    # Check if the custom route exists in the app's routes
    route_paths = [route.path for route in app.routes if isinstance(route, Route)]
    assert "/custom-route" in route_paths


@patch("asyncio.get_event_loop")
@patch("uvicorn.Server")
@patch("uvicorn.Config")
def test_run_app(
    mock_config: MagicMock, mock_server: MagicMock, mock_get_loop: MagicMock, mock_settings: Settings
) -> None:
    app = FastAPI()
    app.state.settings = mock_settings

    mock_loop = MagicMock()
    mock_get_loop.return_value = mock_loop
    server_instance = mock_server.return_value
    # Create a mock coroutine object
    serve_coro = MagicMock()
    server_instance.serve.return_value = serve_coro

    bootstrap.run_app(app)

    mock_config.assert_called_with(
        app,
        host=mock_settings.host,
        port=mock_settings.port,
        log_level="debug",
        reload=True,
        workers=mock_settings.workers,
        limit_max_requests=mock_settings.vps_max_request_size,
        timeout_keep_alive=mock_settings.timeout_keep_alive,
    )
    mock_server.assert_called_with(mock_config.return_value)
    server_instance.serve.assert_called_once()
    # Use the same coroutine object in the assertion
    mock_loop.run_until_complete.assert_called_once_with(serve_coro)


@patch("asyncio.get_event_loop")
@patch("uvicorn.Server")
@patch("uvicorn.Config")
def test_run_app_custom_args(
    mock_config: MagicMock, mock_server: MagicMock, mock_get_loop: MagicMock, mock_settings: Settings
) -> None:
    app = FastAPI()
    app.state.settings = mock_settings

    mock_loop = MagicMock()
    mock_get_loop.return_value = mock_loop
    server_instance = mock_server.return_value
    # Create a mock coroutine object
    serve_coro = MagicMock()
    server_instance.serve.return_value = serve_coro

    bootstrap.run_app(app, reload=False, workers=4)

    mock_config.assert_called_with(
        app,
        host=mock_settings.host,
        port=mock_settings.port,
        log_level="debug",
        reload=False,
        workers=4,
        limit_max_requests=mock_settings.vps_max_request_size,
        timeout_keep_alive=mock_settings.timeout_keep_alive,
    )
    mock_server.assert_called_with(mock_config.return_value)
    server_instance.serve.assert_called_once()
    # Use the same coroutine object in the assertion
    mock_loop.run_until_complete.assert_called_once_with(serve_coro)


@patch("asyncio.get_event_loop")
def test_run_app_signal_handling(mock_get_loop: MagicMock, mock_settings: Settings) -> None:
    if sys.platform == "win32":
        pytest.skip("Signal handling test is not for Windows")

    mock_loop = MagicMock()
    mock_get_loop.return_value = mock_loop

    server_instance = MagicMock()
    server_instance.should_exit = False
    server_instance.serve = MagicMock()

    app = FastAPI()
    app.state.settings = mock_settings

    with patch("uvicorn.Server", return_value=server_instance), patch("uvicorn.Config"):
        bootstrap.run_app(app)

        assert mock_loop.add_signal_handler.call_count == 2

        # Simulate signal
        args, _ = mock_loop.add_signal_handler.call_args_list[0]
        sig, handler, handled_sig, _ = args
        assert sig in (signal.SIGINT, signal.SIGTERM)

        handler(handled_sig, None)
        assert server_instance.should_exit is True
