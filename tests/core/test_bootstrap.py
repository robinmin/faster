"""
Tests for the application bootstrap and factory.
"""

import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import pytest
from pytest_mock import MockerFixture

from faster.core import bootstrap
from faster.core.config import Settings


@pytest.fixture
def mock_settings(mocker: MockerFixture) -> Settings:
    """Fixture for a mock Settings object where debug is False."""
    mock_settings_instance = mocker.MagicMock(spec=Settings)
    mock_settings_instance.app_name = "faster"
    mock_settings_instance.app_version = "0.0.1"
    mock_settings_instance.app_description = "A modern and fast Python web framework"
    mock_settings_instance.environment = "production"
    mock_settings_instance.api_prefix = "/api/v1"
    mock_settings_instance.enable_docs = True
    mock_settings_instance.host = "127.0.0.1"
    mock_settings_instance.port = 8888
    mock_settings_instance.workers = 2
    mock_settings_instance.access_log = True
    mock_settings_instance.limit_concurrency = None
    mock_settings_instance.limit_max_requests = None
    mock_settings_instance.timeout_keep_alive = 5
    mock_settings_instance.ssl_keyfile = None
    mock_settings_instance.ssl_certfile = None
    mock_settings_instance.ssl_version = None
    mock_settings_instance.reload_dirs = []
    mock_settings_instance.reload_includes = []
    mock_settings_instance.reload_excludes = []
    mock_settings_instance.allowed_hosts = ["test.com"]
    mock_settings_instance.database_url = "sqlite+aiosqlite:///:memory:"
    mock_settings_instance.database_pool_size = 20
    mock_settings_instance.database_max_overflow = 0
    mock_settings_instance.database_echo = False
    mock_settings_instance.redis_url = None
    mock_settings_instance.redis_max_connections = 50
    mock_settings_instance.redis_decode_responses = True
    mock_settings_instance.redis_required = False
    mock_settings_instance.celery_broker_url = None
    mock_settings_instance.celery_result_backend = None
    mock_settings_instance.celery_task_always_eager = False
    mock_settings_instance.supabase_url = None
    mock_settings_instance.supabase_anon_key = None
    mock_settings_instance.supabase_service_key = None
    mock_settings_instance.stripe_secret_key = None
    mock_settings_instance.stripe_webhook_secret = None
    mock_settings_instance.stripe_publishable_key = None
    mock_settings_instance.secret_key = None
    mock_settings_instance.jwt_algorithm = "HS256"
    mock_settings_instance.jwt_expiry_minutes = 60
    mock_settings_instance.cors_origins = ["http://test.com"]
    mock_settings_instance.cors_credentials = True
    mock_settings_instance.cors_enabled = True
    mock_settings_instance.cors_allow_methods = ["*"]
    mock_settings_instance.cors_allow_headers = ["*"]
    mock_settings_instance.cors_expose_headers = []
    mock_settings_instance.gzip_enabled = True
    mock_settings_instance.gzip_min_size = 1000
    mock_settings_instance.trusted_hosts = ["*"]
    mock_settings_instance.log_level = "INFO"
    mock_settings_instance.log_format = "json"
    mock_settings_instance.log_file = None
    mock_settings_instance.is_debug = False  # Derived property
    return mock_settings_instance


@pytest.fixture
def mock_debug_settings(mocker: MockerFixture) -> Settings:
    """Fixture for a mock Settings object where debug is True."""
    mock_settings_instance = mocker.MagicMock(spec=Settings)
    mock_settings_instance.app_name = "faster"
    mock_settings_instance.app_version = "0.0.1"
    mock_settings_instance.app_description = "A modern and fast Python web framework"
    mock_settings_instance.environment = "development"
    mock_settings_instance.api_prefix = "/api/v1"
    mock_settings_instance.enable_docs = True
    mock_settings_instance.host = "0.0.0.0"
    mock_settings_instance.port = 8000
    mock_settings_instance.workers = 4
    mock_settings_instance.access_log = True
    mock_settings_instance.limit_concurrency = None
    mock_settings_instance.limit_max_requests = None
    mock_settings_instance.timeout_keep_alive = 5
    mock_settings_instance.ssl_keyfile = None
    mock_settings_instance.ssl_certfile = None
    mock_settings_instance.ssl_version = None
    mock_settings_instance.reload_dirs = []
    mock_settings_instance.reload_includes = []
    mock_settings_instance.reload_excludes = []
    mock_settings_instance.allowed_hosts = ["*"]
    mock_settings_instance.database_url = "sqlite+aiosqlite:///:memory:"
    mock_settings_instance.database_pool_size = 20
    mock_settings_instance.database_max_overflow = 0
    mock_settings_instance.database_echo = False
    mock_settings_instance.redis_url = None
    mock_settings_instance.redis_max_connections = 50
    mock_settings_instance.redis_decode_responses = True
    mock_settings_instance.redis_required = False
    mock_settings_instance.celery_broker_url = None
    mock_settings_instance.celery_result_backend = None
    mock_settings_instance.celery_task_always_eager = False
    mock_settings_instance.supabase_url = None
    mock_settings_instance.supabase_anon_key = None
    mock_settings_instance.supabase_service_key = None
    mock_settings_instance.stripe_secret_key = None
    mock_settings_instance.stripe_webhook_secret = None
    mock_settings_instance.stripe_publishable_key = None
    mock_settings_instance.secret_key = None
    mock_settings_instance.jwt_algorithm = "HS256"
    mock_settings_instance.jwt_expiry_minutes = 60
    mock_settings_instance.cors_origins = ["*"]
    mock_settings_instance.cors_credentials = True
    mock_settings_instance.cors_enabled = True
    mock_settings_instance.cors_allow_methods = ["*"]
    mock_settings_instance.cors_allow_headers = ["*"]
    mock_settings_instance.cors_expose_headers = []
    mock_settings_instance.gzip_enabled = True
    mock_settings_instance.gzip_min_size = 1000
    mock_settings_instance.trusted_hosts = ["*"]
    mock_settings_instance.log_level = "DEBUG"
    mock_settings_instance.log_format = "json"
    mock_settings_instance.log_file = None
    mock_settings_instance.is_debug = True  # Derived property
    return mock_settings_instance


class TestDefaultHandlers:
    """Test the default startup and shutdown handlers."""

    @pytest.mark.asyncio
    async def test_default_startup_handler_returns_true(self, caplog: pytest.LogCaptureFixture) -> None:
        # Arrange
        caplog.set_level(logging.INFO)
        # Act
        result = await bootstrap.default_startup_handler()
        # Assert
        assert result is True
        assert "[faster]: Default startup handler executed." in caplog.text

    @pytest.mark.asyncio
    async def test_default_shutdown_handler_returns_true(self, caplog: pytest.LogCaptureFixture) -> None:
        # Arrange
        caplog.set_level(logging.INFO)
        # Act
        result = await bootstrap.default_shutdown_handler()
        # Assert
        assert result is True
        assert "[faster]: Default shutdown handler executed." in caplog.text


class TestCreateApp:
    """Test the create_app factory function."""

    @pytest.fixture(autouse=True)
    def setup(self, mocker: MockerFixture) -> None:
        # Patch database_manager.initialize to prevent actual database connection during tests
        mocker.patch("faster.core.database.database_manager.initialize", new_callable=AsyncMock)
        mocker.patch("faster.core.database.database_manager.close", new_callable=AsyncMock)

    def test_create_app_returns_fastapi_instance(self, mock_settings: Settings) -> None:
        # Arrange & Act
        app = bootstrap.create_app(settings=mock_settings)
        # Assert
        assert isinstance(app, FastAPI)

    def test_create_app_uses_provided_settings(self, mock_settings: Settings) -> None:
        # Arrange & Act
        app = bootstrap.create_app(settings=mock_settings)
        # Assert
        trusted_host_middleware = next(m for m in app.user_middleware if m.cls is TrustedHostMiddleware)
        assert trusted_host_middleware.kwargs["allowed_hosts"] == mock_settings.allowed_hosts

    def test_create_app_configures_middleware_correctly(self, mock_settings: Settings) -> None:
        # Arrange & Act
        app = bootstrap.create_app(settings=mock_settings)
        # Assert
        middleware_classes = [m.cls for m in app.user_middleware]
        assert GZipMiddleware in middleware_classes
        assert TrustedHostMiddleware in middleware_classes
        assert CORSMiddleware in middleware_classes

    @pytest.mark.parametrize(
        "middleware_cls, expected_options",
        [
            (GZipMiddleware, {"minimum_size": 1000}),
            (TrustedHostMiddleware, {"allowed_hosts": ["test.com"]}),
            (
                CORSMiddleware,
                {
                    "allow_origins": ["http://test.com"],
                    "allow_credentials": True,
                    "allow_methods": ["*"],
                    "allow_headers": ["*"],
                },
            ),
        ],
    )
    def test_middleware_options(
        self, mock_settings: Settings, middleware_cls: Any, expected_options: dict[str, Any]
    ) -> None:
        # Arrange & Act
        app = bootstrap.create_app(settings=mock_settings)
        # Assert
        middleware_instance = next(m for m in app.user_middleware if m.cls is middleware_cls)
        assert isinstance(middleware_instance, Middleware)
        for key, value in expected_options.items():
            assert middleware_instance.kwargs[key] == value

    @pytest.mark.asyncio
    async def test_lifespan_attaches_settings_to_state(self, mock_settings: Settings) -> None:
        # Arrange
        app = bootstrap.create_app(settings=mock_settings)
        # Act
        async with app.router.lifespan_context(app):
            # Assert
            assert app.state.settings == mock_settings

    @pytest.mark.asyncio
    async def test_lifespan_calls_default_handlers(self, mocker: MockerFixture, mock_settings: Settings) -> None:
        # Arrange
        mocker.patch("faster.core.bootstrap.setup_logging")
        startup_spy = mocker.spy(bootstrap, "default_startup_handler")
        shutdown_spy = mocker.spy(bootstrap, "default_shutdown_handler")
        app = bootstrap.create_app(settings=mock_settings)
        # Act
        async with app.router.lifespan_context(app):
            startup_spy.assert_awaited_once()
        shutdown_spy.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lifespan_calls_custom_handlers(self, mock_settings: Settings) -> None:
        # Arrange
        custom_startup = AsyncMock(return_value=True)
        custom_shutdown = AsyncMock(return_value=True)
        app = bootstrap.create_app(
            settings=mock_settings,
            startup_handler=custom_startup,
            shutdown_handler=custom_shutdown,
        )
        # Act
        async with app.router.lifespan_context(app):
            custom_startup.assert_awaited_once()
        custom_shutdown.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lifespan_logs_error_on_startup_failure(
        self, mock_settings: Settings, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Arrange
        caplog.set_level(logging.ERROR)

        async def failing_startup() -> bool:
            return False

        app = bootstrap.create_app(settings=mock_settings, startup_handler=failing_startup)
        # Act
        async with app.router.lifespan_context(app):
            assert "Startup handler failing_startup failed." in caplog.text

    @pytest.mark.asyncio
    async def test_lifespan_logs_error_on_shutdown_failure(
        self, mock_settings: Settings, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Arrange
        caplog.set_level(logging.ERROR)

        async def failing_shutdown() -> bool:
            return False

        app = bootstrap.create_app(settings=mock_settings, shutdown_handler=failing_shutdown)
        # Act
        async with app.router.lifespan_context(app):
            pass
        assert "Shutdown handler failing_shutdown failed." in caplog.text


class TestRunApp:
    """Test the run_app function."""

    @pytest.fixture
    def mock_uvicorn(self, mocker: MockerFixture) -> dict[str, MagicMock]:
        """Fixture to mock uvicorn.Config and uvicorn.Server."""
        config = mocker.patch("uvicorn.Config", autospec=True)
        server = mocker.patch("uvicorn.Server", autospec=True)
        server_instance = server.return_value
        server_instance.serve = AsyncMock()
        return {"config": config, "server": server, "server_instance": server_instance}

    @pytest.fixture
    def mock_loop(self, mocker: MockerFixture) -> MagicMock:
        """Fixture to mock the asyncio event loop."""
        loop_mock = MagicMock(spec=asyncio.AbstractEventLoop)

        async def _run_until_complete_side_effect(coro):
            await coro

        loop_mock.run_until_complete.side_effect = _run_until_complete_side_effect
        loop_mock.add_signal_handler = MagicMock()
        mocker.patch("asyncio.get_event_loop", return_value=loop_mock)
        return loop_mock

    def test_run_app_creates_uvicorn_server_with_correct_config(
        self, mock_settings: Settings, mock_uvicorn: dict[str, MagicMock], mock_loop: MagicMock
    ) -> None:
        # Arrange
        app = bootstrap.create_app(settings=mock_settings)
        app.state.settings = mock_settings
        # Act
        bootstrap.run_app(app)
        # Assert
        mock_uvicorn["config"].assert_called_once_with(
            app,
            host=mock_settings.host,
            port=mock_settings.port,
            log_level="info",
            reload=False,
            workers=mock_settings.workers,
        )
        mock_uvicorn["server"].assert_called_once_with(mock_uvicorn["config"].return_value)
        mock_uvicorn["server_instance"].serve.assert_called_once()
        mock_loop.run_until_complete.assert_called_once()

    def test_run_app_respects_debug_settings(
        self, mock_debug_settings: Settings, mock_uvicorn: dict[str, MagicMock], mock_loop: MagicMock
    ) -> None:
        # Arrange
        app = bootstrap.create_app(settings=mock_debug_settings)
        app.state.settings = mock_debug_settings
        # Act
        bootstrap.run_app(app)
        # Assert
        mock_uvicorn["config"].assert_called_once_with(
            app,
            host=mock_debug_settings.host,
            port=mock_debug_settings.port,
            log_level="debug",
            reload=True,
            workers=mock_debug_settings.workers,
        )

    @pytest.mark.parametrize(
        "reload_arg, workers_arg, expected_reload, expected_workers",
        [
            (True, None, True, 2),
            (False, None, False, 2),
            (None, 4, False, 4),
            (True, 4, True, 4),
        ],
    )
    def test_run_app_overrides_settings_with_args(
        self,
        mock_settings: Settings,
        mock_uvicorn: dict[str, MagicMock],
        mock_loop: MagicMock,
        reload_arg: bool | None,
        workers_arg: int | None,
        expected_reload: bool,
        expected_workers: int,
    ) -> None:
        # Arrange
        app = bootstrap.create_app(settings=mock_settings)
        app.state.settings = mock_settings
        # Act
        bootstrap.run_app(app, reload=reload_arg, workers=workers_arg)
        # Assert
        mock_uvicorn["config"].assert_called_once_with(
            app,
            host=mock_settings.host,
            port=mock_settings.port,
            log_level="info",
            reload=expected_reload,
            workers=expected_workers,
        )

    def test_run_app_sets_up_signal_handlers(
        self, mock_settings: Settings, mock_uvicorn: dict[str, MagicMock], mock_loop: MagicMock, mocker: MockerFixture
    ) -> None:
        # Arrange
        mocker.patch("sys.platform", "linux")
        app = bootstrap.create_app(settings=mock_settings)
        app.state.settings = mock_settings
        # Act
        bootstrap.run_app(app)
        # Assert
        assert mock_loop.add_signal_handler.call_count == 2
        calls = mock_loop.add_signal_handler.call_args_list
        assert any(call.args[0] == 2 for call in calls)
        assert any(call.args[0] == 15 for call in calls)
