from datetime import datetime
import os
from typing import Any, TypeVar, cast

from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from sqlalchemy.sql.elements import ColumnClause, ColumnElement

from .config import Settings

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
    endpoints = []

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
    plugin_health = await app.state.plugin_mgr.check_health()

    db_health = plugin_health.get("database", {})
    redis_health = plugin_health.get("redis", {})
    sentry_health = plugin_health.get("sentry", {})

    # Refresh latest status info
    app.state.latest_status_info = {"db": db_health, "redis": redis_health, "sentry": sentry_health}


###############################################################################
# Query utility functions for SQLModel with proper typing.
#
# This module provides helper functions to cast SQLAlchemy expressions
# to their proper types, helping to avoid mypy errors when working with SQLModel.
#
# Example usage:
#     from .query_utils import qbool, qorder
#
#     query = select(SysMap)
#     query = query.where(qbool(SysMap.category == category))
#     query = query.order_by(qorder(SysMap.order))
###############################################################################


# Type variable for column types
T = TypeVar("T")


def qbool(condition: bool) -> ColumnElement[bool]:
    """
    Cast a boolean condition to a SQLAlchemy ColumnElement[bool].

    This function helps resolve mypy errors when using boolean conditions
    in SQLAlchemy where() clauses with SQLModel.

    Example:
        query = select(SysMap)
        query = query.where(qbool(SysMap.category == category))
        query = query.where(qbool(SysMap.in_used == 1))

    Args:
        condition: A boolean condition expression (e.g., model.field == value)

    Returns:
        ColumnElement[bool]: The condition cast to SQLAlchemy column element
    """
    return cast(ColumnElement[bool], condition)


def qorder(column: Any) -> ColumnClause[Any]:
    """
    Cast a column to a SQLAlchemy ColumnClause for ordering.

    This function helps resolve mypy errors when using columns
    in SQLAlchemy order_by() clauses with SQLModel.

    Example:
        query = select(SysMap)
        query = query.order_by(qorder(SysMap.order))
        query = query.order_by(qorder(SysMap.category))

    Args:
        column: A column reference (e.g., model.field)

    Returns:
        ColumnClause[Any]: The column cast to SQLAlchemy column clause
    """
    return cast(ColumnClause[Any], column)


def qint(column: Any) -> ColumnElement[int]:
    """
    Cast a column to a SQLAlchemy ColumnElement[int].

    This function helps resolve mypy errors when using integer columns
    in SQLAlchemy expressions with SQLModel.

    Example:
        query = select(SysMap)
        query = query.where(qint(SysMap.order) > 5)
        query = query.where(qint(SysMap.some_int_field) == 42)

    Args:
        column: A column reference (e.g., model.field)

    Returns:
        ColumnElement[int]: The column cast to SQLAlchemy column element
    """
    return cast(ColumnElement[int], column)


def qstr(column: Any) -> ColumnElement[str]:
    """
    Cast a column to a SQLAlchemy ColumnElement[str].

    This function helps resolve mypy errors when using string columns
    in SQLAlchemy expressions with SQLModel.

    Example:
        query = select(SysMap)
        query = query.where(qstr(SysMap.category).like('%test%'))
        query = query.where(qstr(SysMap.name).startswith('prefix'))

    Args:
        column: A column reference (e.g., model.field)

    Returns:
        ColumnElement[str]: The column cast to SQLAlchemy column element
    """
    return cast(ColumnElement[str], column)
