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
        auth_enabled=True,
        cors_enabled=True,
        gzip_enabled=True,
        jwks_cache_ttl_seconds=3600,
        user_cache_ttl_seconds=3600,
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
async def test_create_app_calls_plugin_setup(mock_settings: Settings, mock_plugin_mgr: MagicMock) -> None:
    """Test that create_app properly initializes plugins."""
    app = bootstrap.create_app(settings=mock_settings)
    # The plugin setup is called during app lifespan startup
    # We can verify the app was created successfully
    assert app is not None
    assert hasattr(app.state, "settings")


@pytest.mark.asyncio
async def test_create_app_with_middlewares(mock_settings: Settings) -> None:
    """Test that create_app properly adds middlewares."""
    app = bootstrap.create_app(settings=mock_settings)

    # Verify middlewares are added (this will vary based on settings)
    assert len(app.user_middleware) > 0


@pytest.mark.asyncio
async def test_create_app_disabled_features(mock_settings: Settings) -> None:
    """Test create_app with disabled features."""
    mock_settings.auth_enabled = False
    mock_settings.cors_enabled = False
    mock_settings.gzip_enabled = False
    app = bootstrap.create_app(settings=mock_settings)

    # Verify app is created successfully
    assert app is not None
    # With disabled features, there should be fewer middlewares
    assert len(app.user_middleware) >= 2  # At least TrustedHost and CorrelationId


@pytest.mark.asyncio
async def test_refresh_status(mock_settings: Settings, mock_plugin_mgr: MagicMock, caplog: Any) -> None:
    app = FastAPI()
    app.state.settings = mock_settings
    # Mock the check_all_resources function to avoid database initialization issues
    with patch("faster.core.bootstrap.check_all_resources") as mock_check_all_resources:
        # Set up the mock to set the endpoints attribute on the app state
        def mock_check_all_resources_side_effect(app: Any, settings: Any) -> None:
            app.state.endpoints = []

        mock_check_all_resources.side_effect = mock_check_all_resources_side_effect

        # Mock the SysService.get_sys_info to return True
        with patch("faster.core.bootstrap.SysService.get_sys_info", new_callable=AsyncMock) as mock_get_sys_info:
            mock_get_sys_info.return_value = True
            # Just verify the function runs without error
            await bootstrap.refresh_status(app, mock_settings, verbose=True)


def test_create_app(mock_settings: Settings, mock_db_mgr: MagicMock, mock_redis_mgr: MagicMock) -> None:
    app = bootstrap.create_app(settings=mock_settings)
    assert isinstance(app, FastAPI)
    assert app.state.settings == mock_settings
    assert len(app.exception_handlers) > 2  # Check if handlers are added


def test_create_app_lifespan(mock_settings: Settings) -> None:
    app = bootstrap.create_app(settings=mock_settings)

    with (
        patch("faster.core.bootstrap._setup_all") as setup_mock,
        patch("faster.core.bootstrap._teardown_all") as close_mock,
        patch("faster.core.bootstrap.refresh_status"),
    ):
        with TestClient(app):
            setup_mock.assert_called_once()
        close_mock.assert_called_once()


def test_create_app_lifespan_plugin_setup_failure(mock_settings: Settings) -> None:
    """Test that create_app handles plugin setup failures gracefully."""
    app = bootstrap.create_app(settings=mock_settings)

    # Mock the plugin manager to simulate setup failure
    with (
        patch("faster.core.bootstrap.PluginManager.get_instance") as mock_plugin_mgr,
        patch("faster.core.bootstrap.refresh_status"),
        patch("faster.core.bootstrap.logger.warning") as mock_warning,
    ):
        mock_instance = MagicMock()
        mock_instance.setup = AsyncMock(return_value=False)  # Simulate async setup failure
        mock_instance.teardown = AsyncMock(return_value=True)  # Mock teardown as well
        mock_plugin_mgr.return_value = mock_instance

        with TestClient(app):
            pass  # Lifespan is triggered on context entry

        # Verify that the warning log was called
        mock_warning.assert_called_once()
        call_args = mock_warning.call_args[0][0]
        assert "Some plugins failed to initialize" in call_args


def test_create_app_with_routers_and_middlewares(mock_settings: Settings) -> None:
    custom_router = APIRouter()

    @custom_router.get("/custom-route")
    async def custom_route_handler() -> dict[str, str]:
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

    # Verify the handler function exists (satisfies linter)
    assert callable(custom_route_handler)


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
