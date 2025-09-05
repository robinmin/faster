from collections import defaultdict
from datetime import datetime
import os
from typing import Any, TypeVar

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

from .config import Settings
from .exceptions import AppError, AuthError
from .logger import get_logger
from .models import AppResponse
from .plugins import PluginManager
from .sentry import capture_it

###############################################################################

logger = get_logger(__name__)
T = TypeVar("T")


###############################################################################
# Platform Detection Utilities
###############################################################################


def detect_platform(deployment_platform: str) -> str:
    """Detect the current deployment platform.

    Args:
        deployment_platform: The configured deployment platform setting

    Returns:
        str: The detected platform ("vps", "cloudflare-workers")
    """
    if deployment_platform != "auto":
        return deployment_platform

    # Detect Cloudflare Workers environment
    if os.getenv("CF_PAGES") or os.getenv("CF_WORKER"):
        return "cloudflare-workers"

    # Detect common cloud platforms that behave like VPS
    cloud_indicators = [
        "AWS_LAMBDA_FUNCTION_NAME",  # AWS Lambda
        "GOOGLE_CLOUD_PROJECT",  # Google Cloud
        "AZURE_FUNCTIONS_ENVIRONMENT",  # Azure Functions
        "RAILWAY_ENVIRONMENT",  # Railway
        "RENDER_SERVICE_ID",  # Render
        "FLY_APP_NAME",  # Fly.io
        "HEROKU_APP_NAME",  # Heroku
    ]

    for indicator in cloud_indicators:
        if os.getenv(indicator):
            return "vps"  # Treat cloud platforms as VPS-like

    # Default to VPS for standard deployments
    return "vps"


def is_cloudflare_workers(deployment_platform: str) -> bool:
    """Check if running on Cloudflare Workers.

    Args:
        deployment_platform: The configured deployment platform setting

    Returns:
        bool: True if running on Cloudflare Workers
    """
    return detect_platform(deployment_platform) == "cloudflare-workers"


def is_vps_deployment(deployment_platform: str) -> bool:
    """Check if running on VPS or VPS-like environment.

    Args:
        deployment_platform: The configured deployment platform setting

    Returns:
        bool: True if running on VPS or VPS-like environment
    """
    return detect_platform(deployment_platform) == "vps"


###############################################################################
# Request and API Utilities
###############################################################################


def is_api_call(request: Request) -> bool:
    """Check if the request is an API call by checking the Accept header."""

    accept_header = request.headers.get("accept")
    return (accept_header and "application/json" in accept_header) or False


def get_all_endpoints(app: FastAPI) -> list[dict[str, Any]]:
    """
    Return a list of all endpoints with method, path, tags, and function name.
    Includes routes defined via decorators and normal route registration.
    """
    endpoints: list[dict[str, Any]] = []

    for route in app.routes:
        if isinstance(route, APIRoute):
            endpoint_info = {
                "path": route.path,
                "methods": list(route.methods),  # set -> list
                "tags": route.tags or [],
                "name": route.name,  # function name
                "endpoint_func": route.endpoint.__name__,  # actual function name
            }
            endpoints.append(endpoint_info)

    return endpoints


def get_current_endpoint(request: Request, endpoints: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Return the endpoint info for the current request.

    Args:
        request: FastAPI Request object
        endpoints: List returned by get_all_endpoints

    Returns:
        The matching endpoint dict or None if not found
    """
    request_path = request.url.path
    request_method = request.method.upper()

    # TODO: We enabled HEAD method support here, need to check if it's necessary to balance the convinence and security
    for ep in endpoints:
        if request_path == ep.get("path") and (request_method == "HEAD" or request_method in ep.get("methods", [])):
            return ep

    return None


async def check_all_resources(app: FastAPI, settings: Settings) -> None:
    """
    Check the health of all resources using the plugin manager.
    If latest_status_check is too close to now, skip it -- avoid unnecessary checks.
    """
    right_now = datetime.now()
    if (
        hasattr(app.state, "latest_status_check")
        and (right_now - app.state.latest_status_check).total_seconds() < settings.refresh_interval
    ):
        return

    # refresh latest_status_check
    app.state.latest_status_check = right_now

    # Refresh all endpoints
    endpoints = get_all_endpoints(app)
    app.state.endpoints = endpoints

    # Refresh plugin statuses
    plugin_health = await PluginManager.get_instance().check_health()

    db_health = plugin_health.get("database", {})
    redis_health = plugin_health.get("redis", {})
    sentry_health = plugin_health.get("sentry", {})

    # Refresh latest status info
    app.state.latest_status_info = {"db": db_health, "redis": redis_health, "sentry": sentry_health}


###############################################################################
# Query Builders
#
# Query builders have been moved to a separate module for better organization.
# Import them from the builders module:
#
#     from .builders import QueryBuilder, query_builder, soft_delete_query_builder
#
# For backward compatibility, we re-export the main classes here.
###############################################################################


###############################################################################
##  Define all exception  handlers
###############################################################################
async def app_exception_handler(_: Request, exc: AppError) -> AppResponse[Any]:
    """Global exception handler for APIError."""
    ## report to Sentry
    await capture_it(f"Business logic issue: {exc.message}")

    return AppResponse(
        status="error",
        message=exc.message,
        status_code=exc.status_code,
        data=exc.errors if exc.errors else None,
    )


async def custom_validation_exception_handler(_: Request, exc: RequestValidationError) -> AppResponse[Any]:
    """
    Custom global exception handler for Pydantic's RequestValidationError.
    This handler formats the validation errors to be more developer-friendly.
    """
    error_details: defaultdict[str, list[str]] = defaultdict(list)
    for error in exc.errors():
        field = ".".join(map(str, error["loc"])) if error["loc"] else "general"
        error_details[field].append(error["msg"])
    logger.error("Validation error: %s", error_details)
    return AppResponse(
        status="validation error",
        message="Request validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        data=[{"field": k, "messages": v} for k, v in error_details.items()],
    )


async def auth_exception_handler(request: Request, exp: AuthError) -> AppResponse[Any]:
    """Global exception handler for AuthError."""
    logger.error("Authentication error: [%d] %s - %s", exp.status_code, exp.message, exp.errors if exp.errors else None)
    return AppResponse(
        status="Authentication failed",
        message=exp.message,
        status_code=exp.status_code,
        data=exp.errors if exp.errors else None,
    )
