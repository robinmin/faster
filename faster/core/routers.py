from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from .logger import get_logger
from .schemas import AppResponse

logger = get_logger(__name__)

dev_router = APIRouter(prefix="/dev", tags=["dev", "public"])


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
