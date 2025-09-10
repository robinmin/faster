from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .logger import get_logger
from .models import AppResponseDict
from .utilities import check_all_resources

logger = get_logger(__name__)

dev_router = APIRouter(prefix="/dev", tags=["dev", "public"])

sys_router = APIRouter(tags=["public"])


###############################################################################
# Endpoints for dev router
###############################################################################
@dev_router.get("/admin")
async def health_check() -> FileResponse:
    """
    Returns the content of the faster/resources/dev-admin.html file.
    """
    # Define the base directory for templates using a more reliable path
    current_dir = Path(__file__).parent.parent
    file_path = current_dir / "resources" / "dev-admin.html"
    return FileResponse(str(file_path))


@dev_router.get("/settings", response_model=None)
async def settings(request: Request) -> AppResponseDict:
    """
    Returns the settings for dev-admin.
    """

    return AppResponseDict(
        status="success",
        data={
            "supabaseUrl": request.app.state.settings.supabase_url,
            "supabaseKey": request.app.state.settings.supabase_anon_key,
            "backendUrl": request.url.scheme + '://' + request.url.netloc,
            "isSignUp": False,
            "sentryDsn": request.app.state.settings.sentry_client_dsn,
            "sentryEnvironment": request.app.state.settings.environment,
            "sentryEnabled": True,
        },
    )


@dev_router.get("/app_state", response_model=None, tags=["public"])
async def app_state(request: Request) -> AppResponseDict:
    """
    Returns the app state for dev-admin.
    """
    return AppResponseDict(
        data=getattr(request.app.state, "_state", {}),
    )


@dev_router.get("/request_state", response_model=None, tags=["public"])
async def request_state(request: Request) -> AppResponseDict:
    """
    Returns the request state for dev-admin.
    """
    return AppResponseDict(
        data=getattr(request.state, "_state", {}),
    )


###############################################################################
# Endpoints for sys router
###############################################################################
@sys_router.get("/.well-known/appspecific/com.chrome.devtools.json", tags=["public"])
async def chrome_dev_tools(request: Request) -> dict[str, Any]:
    """Chrome DevTools integration endpoint for source code editing in browser."""
    settings = request.app.state.settings

    # Only enable in debug mode
    if not settings.is_debug:
        return {"error": "DevTools endpoint only available in debug mode"}

    return {
        "workspace": {
            "uuid": str(uuid4()),
            "root": Path.cwd(),
        }
    }


@sys_router.get("/metrics", tags=["monitoring"])
async def metrics(request: Request) -> Response:
    """Prometheus metrics endpoint for monitoring."""
    settings = request.app.state.settings

    # Check if metrics are enabled
    if not getattr(settings, "vps_enable_metrics", False):
        return Response("Metrics endpoint disabled", status_code=404)

    try:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except ImportError:
        logger.warning("prometheus_client not installed, metrics endpoint disabled")
        return Response("Metrics not available - prometheus_client not installed", status_code=503)


@sys_router.get("/health", response_model=None)
async def check_health(request: Request) -> AppResponseDict:
    await check_all_resources(request.app, request.app.state.settings)

    latest_status_check = getattr(request.app.state, "latest_status_check", None)
    latest_status_info = getattr(request.app.state, "latest_status_info", {})

    return AppResponseDict(
        data={
            "latest_status_check": latest_status_check,
            "db": latest_status_info.get("db", None),
            "redis": latest_status_info.get("redis", None),
            "sentry": latest_status_info.get("sentry", None),
        },
    )
