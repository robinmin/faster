import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
import logging
import signal
import sys
from types import FrameType
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPError
import uvicorn

from faster.core.auth import router as auth_router
from faster.core.auth.middlewares import AuthMiddleware
from faster.core.auth.services import AuthService

###############################################################################
# import instances
from faster.core.database import db_mgr
from faster.core.exceptions import (
    AppError,
    DBError,
    app_exception_handler,
    custom_validation_exception_handler,
    db_exception_handler,
    http_exception_handler,
)
from faster.core.redis import redis_mgr

from .config import Settings, default_settings
from .logging import setup_logger
from .utilities import get_all_endpoints

logger = logging.getLogger(__name__)


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


async def _setup_all(app: FastAPI, settings: Settings) -> None:
    # Initialize database
    if settings.database_url:
        logger.info("Initializing database...")
        db_mgr.setup(
            settings.database_url,
            settings.database_pool_size,
            settings.database_max_overflow,
            settings.database_echo,
        )

    # Initialize Redis
    if settings.redis_url:
        logger.info("Initializing Redis...")
        try:
            await redis_mgr.setup(
                settings.redis_url,
                decode_responses=bool(settings.redis_decode_responses),
                max_connections=settings.redis_max_connections,
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Redis: {e}")
            if settings.redis_required:
                raise
            # Continue without Redis if it's not required
            logger.info("Continuing without Redis as it's not required")


async def _close_all(app: FastAPI) -> None:
    # Close database connection
    logger.info("Closing database connection...")
    await db_mgr.close()

    # Close Redis connection
    logger.info("Closing Redis connection...")
    await redis_mgr.close()


async def refresh_status(app: FastAPI, settings: Settings, verbose: bool = False) -> None:
    # Refresh all endpoints
    endpoints = get_all_endpoints(app)
    app.state.endpoints = endpoints

    # Refresh db status
    db_health = await db_mgr.check_health()

    # Refresh redis status
    redis_health = await redis_mgr.check_health()

    if verbose:
        logger.info("=========================================================")
        logger.info(
            f"\tWe are running '{settings.app_name}' - {settings.app_version} on {settings.environment} in {'DEBUG' if settings.is_debug else 'NON-DEBUG'} mode."
        )
        if "master" not in db_health or not db_health["master"]:
            logger.error(f"\tDB: {db_health}")
        else:
            logger.info(f"\tDB: {db_health}")

        # Only show Redis error if it's required or if there was an attempt to connect
        if "master" not in redis_health or not redis_health["master"]:
            if settings.redis_required or (settings.redis_url and redis_health.get("master") is False):
                logger.error(f"\tRedis: {redis_health}")
            elif settings.redis_url:
                logger.warning(f"\tRedis: {redis_health}")
        else:
            logger.info(f"\tRedis: {redis_health}")

        if settings.is_debug:
            logger.debug("=========================================================")
            logger.debug("All available URLs:")
            for endpoint in endpoints:
                logger.debug(
                    f"  [{'/'.join(endpoint['methods'])}] {endpoint['path']} - {endpoint['name']} \t# {', '.join(endpoint['tags'])} "
                )

        logger.info("=========================================================")


def create_app(
    settings: Settings | None = None,
    startup_handler: Callable[..., Awaitable[bool]] | None = None,
    shutdown_handler: Callable[..., Awaitable[bool]] | None = None,
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
        ["uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"],
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        logger.info("Starting application...")
        logger.info("Initializing resources...")
        await _setup_all(app, settings)
        try:
            final_startup_handler = startup_handler or default_startup_handler
            if not await final_startup_handler():
                logger.error(f"Startup handler {getattr(final_startup_handler, '__name__', 'unknown')} failed.")
        except Exception as e:
            logger.error(f"Error during startup: {e}")

        await refresh_status(app, settings, settings.is_debug)

        ########################################################################
        yield
        ########################################################################

        logger.info("Shutting down resources...")
        await _close_all(app)

        logger.info("Shutting down application...")
        try:
            final_shutdown_handler = shutdown_handler or default_shutdown_handler
            if not await final_shutdown_handler():
                logger.error(f"Shutdown handler {getattr(final_shutdown_handler, '__name__', 'unknown')} failed.")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

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

    # Configure and add middleware to the FastAPI application
    # NOTE: Middleware must be added before initializing database/Redis to avoid "Cannot add middleware after an application has started" error
    if settings.gzip_enabled:
        app.add_middleware(GZipMiddleware, minimum_size=settings.gzip_min_size)

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts or ["*"])

    if settings.jwt_secret_key:
        app.add_middleware(
            AuthMiddleware,
            auth_service=AuthService(
                jwt_secret=settings.jwt_secret_key,
                algorithms=(settings.jwt_algorithm.split(",") if settings.jwt_algorithm else None),
                expiry_minutes=settings.jwt_expiry_minutes,
            ),
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

    # Include routers and exception handlers
    app.include_router(auth_router)

    app.add_exception_handler(AppError, app_exception_handler)  # type: ignore
    app.add_exception_handler(DBError, db_exception_handler)  # type: ignore
    app.add_exception_handler(StarletteHTTPError, http_exception_handler)  # type: ignore
    app.add_exception_handler(RequestValidationError, custom_validation_exception_handler)  # type: ignore

    return app


def run_app(
    app: FastAPI,
    reload: bool | None = None,
    workers: int | None = None,
    **kwargs: Any,
) -> None:
    """
    Run the FastAPI application using uvicorn.

    Args:
        app: The FastAPI application instance.
        reload: Whether to enable auto-reloading.
        workers: The number of worker processes.
        **kwargs: Other uvicorn parameters.
    """
    settings = app.state.settings if hasattr(app.state, "settings") else default_settings

    log_level = "debug" if settings.is_debug else "info"
    use_reload = reload if reload is not None else settings.is_debug

    config = uvicorn.Config(
        app,
        host=settings.host,
        port=settings.port,
        log_level=log_level,
        reload=use_reload,
        workers=workers or settings.workers,
        **kwargs,
    )

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
