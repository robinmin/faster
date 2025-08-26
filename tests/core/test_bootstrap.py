import logging
import signal
import sys
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
import pytest

from faster.core import bootstrap
from faster.core.config import Settings

# Individual tests are marked with @pytest.mark.asyncio as needed


@pytest.fixture
def mock_settings():
    """Fixture for mock settings."""
    return Settings(
        app_name="Test App",
        app_version="0.1.0",
        environment="development",
        is_debug=True,
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost",
        jwt_secret_key="test-secret",
        auth_endabled=True,
        cors_enabled=True,
        gzip_enabled=True,
    )


@pytest.fixture
def mock_db_mgr():
    """Fixture for mocking db_mgr."""
    with patch("faster.core.bootstrap.db_mgr", new_callable=MagicMock) as mock:
        mock.setup = AsyncMock()
        mock.close = AsyncMock()
        mock.check_health = AsyncMock(return_value={"master": True})
        yield mock


@pytest.fixture
def mock_redis_mgr():
    """Fixture for mocking redis_mgr."""
    with patch("faster.core.bootstrap.redis_mgr", new_callable=MagicMock) as mock:
        mock.setup = AsyncMock()
        mock.close = AsyncMock()
        mock.check_health = AsyncMock(return_value={"ping": True})
        yield mock


@pytest.fixture
def mock_auth_service():
    """Fixture for mocking AuthService."""
    with patch("faster.core.bootstrap.AuthService", new_callable=MagicMock) as mock:
        yield mock


@pytest.mark.asyncio
async def test_default_startup_handler():
    assert await bootstrap.default_startup_handler() is True


@pytest.mark.asyncio
async def test_default_shutdown_handler():
    assert await bootstrap.default_shutdown_handler() is True


@pytest.mark.asyncio
async def test_setup_all(mock_settings, mock_db_mgr, mock_redis_mgr):
    app = FastAPI()
    await bootstrap._setup_all(app, mock_settings)

    mock_db_mgr.setup.assert_called_once_with(
        mock_settings.database_url,
        mock_settings.database_pool_size,
        mock_settings.database_max_overflow,
        mock_settings.database_echo,
    )
    mock_redis_mgr.setup.assert_called_once()


@pytest.mark.asyncio
async def test_setup_all_no_db_url(mock_settings, mock_db_mgr, mock_redis_mgr):
    mock_settings.database_url = None
    app = FastAPI()
    await bootstrap._setup_all(app, mock_settings)

    mock_db_mgr.setup.assert_not_called()
    mock_redis_mgr.setup.assert_called_once()


@pytest.mark.asyncio
async def test_teardown_all(mock_db_mgr, mock_redis_mgr):
    app = FastAPI()
    await bootstrap._teardown_all(app)

    mock_db_mgr.close.assert_called_once()
    mock_redis_mgr.close.assert_called_once()


def test_setup_middlewares(mock_settings, mock_auth_service):
    app = FastAPI()
    bootstrap._steup_middlewares(app, mock_settings)

    # Gzip, TrustedHost, Auth, AuthProxy, CORS
    assert len(app.user_middleware) == 4


def test_setup_middlewares_disabled(mock_settings):
    mock_settings.auth_endabled = False
    mock_settings.cors_enabled = False
    mock_settings.gzip_enabled = False
    app = FastAPI()
    bootstrap._steup_middlewares(app, mock_settings)

    # Only TrustedHost
    assert len(app.user_middleware) == 1


@pytest.mark.asyncio
async def test_refresh_status(mock_settings, mock_db_mgr, mock_redis_mgr, caplog):
    app = FastAPI()
    with caplog.at_level(logging.INFO):
        await bootstrap.refresh_status(app, mock_settings, verbose=True)

    assert "We are running 'Test App' - 0.1.0" in caplog.text
    assert "DB: {'master': True}" in caplog.text
    assert "Redis: {'ping': True}" in caplog.text
    mock_db_mgr.check_health.assert_called_once()
    mock_redis_mgr.check_health.assert_called_once()


def test_create_app(mock_settings, mock_db_mgr, mock_redis_mgr):
    app = bootstrap.create_app(settings=mock_settings)
    assert isinstance(app, FastAPI)
    assert app.state.settings == mock_settings
    assert len(app.exception_handlers) > 2  # Check if handlers are added


def test_create_app_lifespan(mock_settings):
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


def test_create_app_lifespan_startup_fails(mock_settings, caplog):
    startup_mock = AsyncMock(return_value=False)
    startup_mock.__name__ = "startup_mock"
    app = bootstrap.create_app(settings=mock_settings, startup_handler=startup_mock)

    # The exception is caught and logged, but not re-raised by default.
    # So we check the log instead of expecting a raised exception.
    with (
        patch("faster.core.bootstrap._setup_all"),
        patch("faster.core.bootstrap.refresh_status"),
        caplog.at_level(logging.CRITICAL),
    ):
        with TestClient(app):
            pass  # Lifespan is triggered on context entry
        assert "Application startup failed" in caplog.text
        assert "Startup handler startup_mock failed" in caplog.text

    startup_mock.assert_called_once()


def test_create_app_with_routers_and_middlewares(mock_settings):
    custom_router = APIRouter()

    @custom_router.get("/custom-route")
    async def my_custom_route():
        return {"message": "success"}

    class CustomMiddleware:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            await self.app(scope, receive, send)

    app = bootstrap.create_app(
        settings=mock_settings,
        routers=[custom_router],
        middlewares=[CustomMiddleware],
    )

    # Gzip, TrustedHost, Auth, AuthProxy, CORS, Custom
    assert len(app.user_middleware) == 5

    # Check if the custom route exists in the app's routes
    route_paths = [route.path for route in app.routes]
    assert "/custom-route" in route_paths


@patch("asyncio.get_event_loop")
@patch("uvicorn.Server")
@patch("uvicorn.Config")
def test_run_app(mock_config, mock_server, mock_get_loop, mock_settings):
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
    )
    mock_server.assert_called_with(mock_config.return_value)
    server_instance.serve.assert_called_once()
    # Use the same coroutine object in the assertion
    mock_loop.run_until_complete.assert_called_once_with(serve_coro)


@patch("asyncio.get_event_loop")
@patch("uvicorn.Server")
@patch("uvicorn.Config")
def test_run_app_custom_args(mock_config, mock_server, mock_get_loop, mock_settings):
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
    )
    mock_server.assert_called_with(mock_config.return_value)
    server_instance.serve.assert_called_once()
    # Use the same coroutine object in the assertion
    mock_loop.run_until_complete.assert_called_once_with(serve_coro)


@patch("asyncio.get_event_loop")
def test_run_app_signal_handling(mock_get_loop, mock_settings):
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
