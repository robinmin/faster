import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
import logging
import signal
import sys
from types import FrameType
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import uvicorn

from faster.core.database import database_manager
from faster.core.redis import redis_manager

from .config import Settings, default_settings
from .logging import setup_logging
from .schemas import APIResponse

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


async def default_exception_handler(request: Request, exc: Exception) -> APIResponse[Any]:
    """
    Default exception handler for all unhandled exceptions.
    Logs the exception and returns a a generic JSON response.
    """
    status_code = 500
    detail = "Internal Server Error"

    logger.error(f"Exception caught: {status_code} - {detail} - {exc}", exc_info=True)
    return APIResponse(
        status="error",
        message=detail,
        status_code=status_code,
    )


class AppError(Exception):
    def __init__(self, message: str, code: str, status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code


async def app_exception_handler(request: Request, exc: Exception) -> APIResponse[Any]:
    status_code = 500
    code = "internal_error"
    message = "Internal Server Error"

    if isinstance(exc, AppError):
        status_code = exc.status_code
        code = exc.code
        message = exc.message

    logger.error(
        "app_error",
        exc_info=True,
        extra={"code": code, "message": message, "path": request.url.path},
    )
    return APIResponse(
        status="error",
        message=message,
        status_code=status_code,
        data={code: code},
    )


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

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Setup logging as early as possible to ensure logs are captured
        setup_logging(settings.is_debug)

        # Startup: Initialize settings and attach to app.state
        app.state.settings = settings

        # Initialize database
        logger.info("Initializing database...")
        await database_manager.initialize(
            settings.database_url,
            settings.database_pool_size,
            settings.database_max_overflow,
            settings.database_echo,
            is_debug=settings.is_debug,
        )

        # Initialize Redis
        if settings.redis_url:
            logger.info("Initializing Redis...")
            await redis_manager.initialize(
                settings.redis_url,
                settings.redis_max_connections,
                settings.redis_decode_responses,
            )

        # Determine and run the final startup handler
        logger.info("Starting application...")
        try:
            final_startup_handler = startup_handler or default_startup_handler
            if not await final_startup_handler():
                logger.error(f"Startup handler {getattr(final_startup_handler, '__name__', 'unknown')} failed.")
        except Exception as e:
            logger.error(f"Error during startup: {e}")

        yield

        # Shutdown: Clean up resources if necessary
        logger.info("Shutting down application...")
        # Close database connection
        logger.info("Closing database connection...")
        await database_manager.close()
        logger.info("Database connection closed.")

        # Close Redis connection
        logger.info("Closing Redis connection...")
        await redis_manager.close()
        logger.info("Redis connection closed.")
        try:
            final_shutdown_handler = shutdown_handler or default_shutdown_handler
            if not await final_shutdown_handler():
                logger.error(f"Shutdown handler {getattr(final_shutdown_handler, '__name__', 'unknown')} failed.")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    app = FastAPI(lifespan=lifespan, **kwargs)

    # Add essential middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts or ["*"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # TODO: Include routers from your modules here
    # from my_module import routers as my_module_routers
    # app.include_router(my_module_routers.router)

    # Add custom exception handlers here
    app.add_exception_handler(AppError, app_exception_handler)
    app.add_exception_handler(Exception, default_exception_handler)

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
    use_reload = reload or settings.is_debug

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
