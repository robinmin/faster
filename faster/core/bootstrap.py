import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import os
import signal
import sys
from types import FrameType
from typing import Any
from uuid import uuid4

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import APIRouter, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
import uvicorn

from .auth import router as auth_router
from .auth.middlewares import AuthMiddleware
from .auth.services import AuthService
from .config import Settings, default_settings, get_default_allowed_paths
from .database import DatabaseManager
from .exceptions import (
    AppError,
    AuthError,
)
from .logger import get_logger, setup_logger
from .plugins import PluginManager
from .redis import RedisManager
from .routers import dev_router, sys_router
from .sentry import SentryManager
from .services import SysService
from .utilities import (
    app_exception_handler,
    auth_exception_handler,
    check_all_resources,
    custom_validation_exception_handler,
    is_cloudflare_workers,
    is_vps_deployment,
)

###############################################################################

logger = get_logger(__name__)


async def _setup_vps_specific(app: FastAPI, settings: Settings) -> None:
    """Setup VPS-specific configurations."""
    logger.info("Configuring for VPS deployment...")

    # Add static file serving if configured
    if settings.vps_static_files_path and os.path.exists(settings.vps_static_files_path):
        app.mount("/static", StaticFiles(directory=settings.vps_static_files_path), name="static")
        logger.info(f"Static files mounted at: {settings.vps_static_files_path}")

    # Note: Metrics endpoint is now in sys_router

    # Configure for reverse proxy if needed
    if settings.vps_reverse_proxy:
        logger.info("Configured for reverse proxy deployment")


def _register_all_plugins(app: FastAPI) -> None:
    """Register core plugins."""
    plugin_mgr = PluginManager.get_instance()

    # Register core plugins
    plugin_mgr.register("database", DatabaseManager.get_instance())
    plugin_mgr.register("redis", RedisManager.get_instance())
    plugin_mgr.register("sentry", SentryManager.get_instance())
    plugin_mgr.register("auth", AuthService.get_instance())
    logger.debug("Plugin manager setup complete")


async def _setup_all(app: FastAPI, settings: Settings) -> None:
    # VPS-specific setup (metrics, static files)
    if is_vps_deployment(settings.deployment_platform):
        await _setup_vps_specific(app, settings)

    # Initialize all plugins through plugin manager
    logger.info("Initializing all plugins...")
    success = await PluginManager.get_instance().setup(settings)
    if not success:
        logger.warning("Some plugins failed to initialize, but continuing startup")


async def _teardown_all(app: FastAPI) -> None:
    # Use plugin system for teardown
    logger.info("Tearing down all plugins...")
    success = await PluginManager.get_instance().teardown()
    if not success:
        logger.warning("Some plugins failed to teardown properly")


def _add_middlewares(app: FastAPI, settings: Settings, middlewares: list[Any] | None = None) -> None:
    # Configure and add middleware to the FastAPI application
    # NOTE: Middleware must be added before initializing database/Redis to avoid "Cannot add middleware after an application has started" error

    # Compression middleware
    if settings.gzip_enabled:
        app.add_middleware(GZipMiddleware, minimum_size=settings.gzip_min_size)

    # Trusted hosts middleware
    trusted_hosts = settings.allowed_hosts or ["*"]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

    # Always add AuthMiddleware, but it will check settings.auth_enabled internally
    app.add_middleware(
        AuthMiddleware,
        allowed_paths=get_default_allowed_paths(),
        require_auth=settings.auth_enabled,
    )

    if settings.cors_enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=settings.cors_credentials,
            allow_methods=settings.cors_allow_methods,
            allow_headers=settings.cors_allow_headers,
            expose_headers=settings.cors_expose_headers,
        )

    ## add x-request-id header to each request for tracing
    app.add_middleware(
        CorrelationIdMiddleware,
        header_name="X-Request-ID",
        # update_request_header=True,
        generator=lambda: uuid4().hex,
        # validator=is_valid_uuid4,
        # transformer=lambda a: a,
    )

    # TODO: Someone says this is not necessary and recommended, we will remove it later if confirmed
    app.add_middleware(SentryAsgiMiddleware)

    # Add custom middlewares
    if middlewares:
        for middleware in middlewares:
            app.add_middleware(middleware)


async def refresh_status(app: FastAPI, settings: Settings, verbose: bool = False) -> None:
    """
    Refresh status of all services using the plugin manager.
    If verbose is True, log the status of each service.
    If latest_status_check is too close to now, skip it -- avoid unnecessary checks.
    """
    await check_all_resources(app, app.state.settings)

    # Load system information into redis cache
    service = SysService()
    if not await service.get_sys_info():
        logger.error("Failed to load system information from database into Redis")

    # Get AuthService instance for refresh_data call
    auth_service = AuthService.get_instance()

    # Use refresh_data method to prepare authentication data
    _ = await auth_service.refresh_data(app, is_debug=settings.is_debug)

    if not verbose:
        return

    logger.debug("=========================================================")
    logger.debug(
        f"\tWe are running '{settings.app_name}' - {settings.app_version} on {settings.environment} in {'DEBUG' if settings.is_debug else 'NON-DEBUG'} mode."
    )

    latest_status_info = getattr(app.state, "latest_status_info", {})
    db_health = latest_status_info.get("db", {})
    redis_health = latest_status_info.get("redis", {})
    sentry_health = latest_status_info.get("sentry", {})
    auth_health = latest_status_info.get("auth", {})

    if db_health.get("master", False):
        logger.debug(f"\tDB\t: {db_health}")
    else:
        logger.error(f"\tDB\t: {db_health}")

    # Only show Redis error if it's required or if there was an attempt to connect
    if redis_health.get("ping", False):
        logger.debug(f"\tRedis\t: {redis_health}")
    elif settings.redis_enabled or (settings.redis_url and redis_health.get("ping") is False):
        logger.error(f"\tRedis\t: {redis_health}")
    elif settings.redis_url:
        logger.warning(f"\tRedis\t: {redis_health}")

    logger.debug(f"\tSentry\t: {sentry_health}")
    logger.debug(f"\tAuth\t: {auth_health}")

    logger.debug("=========================================================")


def create_app(
    settings: Settings | None = None,
    routers: list[APIRouter] | None = None,
    middlewares: list[Any] | None = None,
    **kwargs: Any,
) -> FastAPI:
    """
    Create a FastAPI application.

    Args:
        settings: The configuration object. If None, it's retrieved automatically.
        routers: List of additional routers to include.
        middlewares: List of additional middlewares to add.
        **kwargs: Other FastAPI parameters.

    Returns:
        A FastAPI application instance.
    """

    if settings is None:
        settings = default_settings

    # Setup logging as early as possible to ensure logs are captured
    setup_logger(
        settings.is_debug,
        settings.log_level,
        settings.log_format,
        settings.log_file,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        logger.info("Starting application...")
        try:
            logger.info("Setting up all resources...")
            await _setup_all(app, settings)

            await refresh_status(app, settings, settings.is_debug)
        except AppError as exp:
            logger.critical(f"Application startup failed: {exp}")

        try:
            yield  # Still yield to allow lifespan to complete
        except AppError as exp:
            logger.critical(f"Application error: {exp}")

        try:
            logger.info("Tearing down all resources...")
            await _teardown_all(app)

            logger.info("Shutting down application...")
        except AppError as e:
            logger.critical(f"Error during shutdown: {e}")

    # FastAPI configuration
    app = FastAPI(
        lifespan=lifespan,
        docs_url="/docs" if settings.is_debug else None,
        redoc_url="/redoc" if settings.is_debug else None,
        openapi_url="/openapi.json" if settings.is_debug else None,
        version=settings.app_version,
        title=settings.app_name,
        description=settings.app_description,
        debug=settings.is_debug,
        **kwargs,
    )
    app.state.settings = settings

    # Register core plugins
    _register_all_plugins(app)

    # Add middlewares
    _add_middlewares(app, settings, middlewares)

    # Include routers
    app.include_router(auth_router)
    app.include_router(sys_router)
    if settings.is_debug:
        app.include_router(dev_router)

    # Include custom routers
    if routers:
        for router in routers:
            app.include_router(router)

    # Include exception handlers
    app.add_exception_handler(RequestValidationError, custom_validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AuthError, auth_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AppError, app_exception_handler)  # type: ignore[arg-type]

    return app


def run_app(
    app: FastAPI,
    reload: bool | None = None,
    workers: int | None = None,
    **kwargs: Any,
) -> None:
    """
    Run the FastAPI application using appropriate server for the platform.

    Args:
        app: The FastAPI application instance.
        reload: Whether to enable auto-reloading.
        workers: The number of worker processes.
        **kwargs: Other uvicorn parameters.
    """
    settings = app.state.settings if hasattr(app.state, "settings") else default_settings

    # Platform-specific server configuration
    if is_cloudflare_workers(settings.deployment_platform):
        logger.warning("run_app() should not be called for Cloudflare Workers deployment")
        logger.info("Use wrangler or direct ASGI export for Cloudflare Workers")
        return

    log_level = "debug" if settings.is_debug else "info"
    use_reload = reload if reload is not None else settings.is_debug

    # Auto-scaling workers
    final_workers = workers or settings.workers
    if settings.auto_scale_workers:
        cpu_count = os.cpu_count() or 1
        final_workers = min(max(settings.min_workers, cpu_count), settings.max_workers)
        logger.info(f"Auto-scaling workers: {final_workers} (CPU count: {cpu_count})")

    # Server configuration
    config_kwargs: dict[str, Any] = {
        "host": settings.host,
        "port": settings.port,
        "log_level": log_level,
        "reload": use_reload,
        "workers": final_workers,
    }

    # Optional server settings
    if settings.vps_max_request_size:
        config_kwargs["limit_max_requests"] = settings.vps_max_request_size
    if settings.timeout_keep_alive:
        config_kwargs["timeout_keep_alive"] = settings.timeout_keep_alive

    # Add any additional kwargs passed by user
    config_kwargs.update(kwargs)

    config = uvicorn.Config(app, **config_kwargs)

    server = uvicorn.Server(config)

    # Graceful shutdown
    loop = asyncio.get_event_loop()

    def handle_signal(sig: int, frame: FrameType | None) -> None:
        logger.warning(f"Received signal {sig}, shutting down...")
        server.should_exit = True
        # Further cleanup can be done here if needed

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal, sig, None)

    loop.run_until_complete(server.serve())
