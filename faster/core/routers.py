from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .logger import get_logger
from .schemas import AppResponse

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
async def settings(request: Request) -> AppResponse[dict[str, Any]]:
    """
    Returns the settings for dev-admin.
    """

    return AppResponse(
        status="success",
        data={
            "supabaseUrl": request.app.state.settings.supabase_url,
            "supabaseKey": request.app.state.settings.supabase_anon_key,
            "backendUrl": "http://127.0.0.1:8000",
            "isSignUp": False,
            "sentryDsn": request.app.state.settings.sentry_client_dsn,
            "sentryEnvironment": request.app.state.settings.environment,
            "sentryEnabled": True,
        },
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
