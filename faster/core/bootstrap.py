import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
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
from .database import db_mgr
from .exceptions import (
    AppError,
    AuthError,
    app_exception_handler,
    auth_exception_handler,
    custom_validation_exception_handler,
)
from .logger import get_logger, setup_logger
from .redis import redis_mgr
from .routers import dev_router, sys_router
from .sentry import SentryManager
from .utilities import get_all_endpoints, is_cloudflare_workers, is_vps_deployment

###############################################################################

logger = get_logger(__name__)
sentry_mgr = SentryManager.get_instance()


async def default_startup_handler() -> bool:
    """
    Default startup handler that can be overridden.
    Returns True if successful, False otherwise.
    """
    logger.info("[faster]: Default startup handler executed.")

    return True


async def default_shutdown_handler() -> bool:
    """
    Default shutdown handler that can be overridden.
    Returns True if successful, False otherwise.
    """
    logger.info("[faster]: Default shutdown handler executed.")
    return True


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


async def _setup_all(app: FastAPI, settings: Settings) -> None:
    # VPS-specific setup (metrics, static files)
    if is_vps_deployment(settings.deployment_platform):
        await _setup_vps_specific(app, settings)

    # Initialize database
    if settings.database_url:
        logger.info("Initializing database...")
        await db_mgr.setup(
            settings.database_url,
            settings.database_pool_size,
            settings.database_max_overflow,
            settings.database_echo,
        )

    logger.info("Initializing Sentry...")
    await sentry_mgr.setup(
        dsn=settings.sentry_dsn,
        trace_sample_rate=settings.sentry_trace_sample_rate,
        profiles_sample_rate=settings.sentry_profiles_sample_rate,
        environment=settings.environment,
    )

    # Initialize Redis
    if settings.redis_url:
        logger.info("Initializing Redis...")
        await redis_mgr.setup(
            provider=settings.redis_provider,
            redis_url=settings.redis_url,
            password=settings.redis_password,
            max_connections=settings.redis_max_connections,
            decode_responses=settings.redis_decode_responses,
            fallback_to_fake=settings.is_debug,
        )


async def _teardown_all(app: FastAPI) -> None:
    # Close database connection
    logger.info("Closing database connection...")
    await db_mgr.close()

    # Close Redis connection
    logger.info("Closing Redis connection...")
    await redis_mgr.close()

    # Close Sentry connection
    logger.info("Closing Sentry connection...")
    await sentry_mgr.close()


def _steup_middlewares(app: FastAPI, settings: Settings, middlewares: list[Any] | None = None) -> None:
    # Configure and add middleware to the FastAPI application
    # NOTE: Middleware must be added before initializing database/Redis to avoid "Cannot add middleware after an application has started" error

    # Compression middleware
    if settings.gzip_enabled:
        app.add_middleware(GZipMiddleware, minimum_size=settings.gzip_min_size)

    # Trusted hosts middleware
    trusted_hosts = settings.allowed_hosts or ["*"]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

    if settings.auth_endabled:
        jwks_url = settings.supabase_jwks_url
        if not jwks_url:
            jwks_url = (settings.supabase_url or "") + "/auth/v1/.well-known/jwks.json"

        auth_service = AuthService(
            jwt_secret=settings.jwt_secret_key or "",
            algorithms=(settings.jwt_algorithm.split(",") if settings.jwt_algorithm else None),
            expiry_minutes=settings.jwt_expiry_minutes,
            supabase_url=settings.supabase_url or "",
            supabase_anon_key=settings.supabase_anon_key or "",
            supabase_service_key=settings.supabase_service_key or "",
            supabase_jwks_url=jwks_url,
            # supabase_client_id = settings.supabase_client_id or "",
            supabase_audience=settings.supabase_audience or "",
            auto_refresh_jwks=settings.auto_refresh_jwks,
        )
        app.add_middleware(
            AuthMiddleware,
            auth_service=auth_service,
            allowed_paths=get_default_allowed_paths(),
            require_auth=True,
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

    # Add custom middlewares
    if middlewares:
        for middleware in middlewares:
            app.add_middleware(middleware)


async def refresh_status(app: FastAPI, settings: Settings, verbose: bool = False) -> None:
    # Refresh all endpoints
    endpoints = get_all_endpoints(app)
    app.state.endpoints = endpoints

    # Refresh db status
    db_health = await db_mgr.check_health()

    # Refresh redis status
    redis_health = await redis_mgr.check_health()

    # Refresh Sentry status
    sentry_health = await sentry_mgr.check_health()

    if verbose:
        logger.info("=========================================================")
        logger.info(
            f"\tWe are running '{settings.app_name}' - {settings.app_version} on {settings.environment} in {'DEBUG' if settings.is_debug else 'NON-DEBUG'} mode."
        )
        if "master" not in db_health or not db_health["master"]:
            logger.error(f"\tDB\t: {db_health}")
        else:
            logger.info(f"\tDB\t: {db_health}")

        # Only show Redis error if it's required or if there was an attempt to connect
        if redis_health.get("ping"):
            logger.info(f"\tRedis\t: {redis_health}")
        elif settings.redis_enabled or (settings.redis_url and redis_health.get("ping") is False):
            logger.error(f"\tRedis\t: {redis_health}")
        elif settings.redis_url:
            logger.warning(f"\tRedis\t: {redis_health}")

        logger.info(f"\tSentry\t: {sentry_health}")

        if settings.is_debug:
            logger.debug("=========================================================")
            logger.debug("All available URLs:")
            for endpoint in endpoints:
                logger.debug(
                    f"  [{'/'.join(endpoint['methods'])}] {endpoint['path']} - {endpoint['name']} \t# {', '.join(endpoint['tags'])} "
                )

        logger.info("=========================================================")


def create_app(  # noqa: C901
    settings: Settings | None = None,
    startup_handler: Callable[..., Awaitable[bool]] | None = None,
    shutdown_handler: Callable[..., Awaitable[bool]] | None = None,
    routers: list[APIRouter] | None = None,
    middlewares: list[Any] | None = None,
    **kwargs: Any,
) -> FastAPI:
    """
    Create a FastAPI application.

    Args:
        settings: The configuration object. If None, it's retrieved automatically.
        startup_handler: An async handler to call on startup.
        shutdown_handler: An async handler to call on shutdown.
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

            final_startup_handler = startup_handler or default_startup_handler
            if not await final_startup_handler():
                raise AppError(f"Startup handler {getattr(final_startup_handler, '__name__', 'unknown')} failed.")

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
            final_shutdown_handler = shutdown_handler or default_shutdown_handler
            if not await final_shutdown_handler():
                logger.error(f"Shutdown handler {getattr(final_shutdown_handler, '__name__', 'unknown')} failed.")
        except AppError as e:
            logger.critical(f"Error during shutdown: {e}")

    # FastAPI configuration
    docs_url = "/docs" if settings.is_debug else None
    redoc_url = "/redoc" if settings.is_debug else None
    openapi_url = "/openapi.json" if settings.is_debug else None

    app = FastAPI(
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        version=settings.app_version,
        title=settings.app_name,
        description=settings.app_description,
        debug=settings.is_debug,
        **kwargs,
    )
    app.state.settings = settings

    # Setup middlewares
    _steup_middlewares(app, settings, middlewares)

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
    # Someone says this is not necessary and recommended, we will remove it later if confirmed
    app.add_middleware(SentryAsgiMiddleware)

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
