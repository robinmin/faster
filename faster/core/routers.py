from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .auth.routers import get_auth_service
from .auth.services import AuthService
from .client_generator import ClientConfig, ClientGenerator
from .logger import get_logger
from .models import (
    AppResponseDict,
    SysDictAdjustRequest,
    SysDictDeleteRequest,
    SysDictShowRequest,
    SysMapAdjustRequest,
    SysMapDeleteRequest,
    SysMapShowRequest,
)
from .services import SysService
from .utilities import check_all_resources

logger = get_logger(__name__)

dev_router = APIRouter(prefix="/dev", tags=["dev"])

sys_router = APIRouter(tags=["sys"])


###############################################################################
# Endpoints for dev router
###############################################################################
@dev_router.get("/admin", tags=["public"])
async def admin_login() -> FileResponse:
    """
    Returns the content of the faster/resources/dev-admin.html file.
    """
    # Define the base directory for templates using a more reliable path
    current_dir = Path(__file__).parent.parent
    file_path = current_dir / "resources" / "dev-admin.html"
    return FileResponse(str(file_path))


@dev_router.get("/settings", response_model=None, tags=["public"])
async def settings(request: Request) -> AppResponseDict:
    """
    Returns the settings for dev-admin.
    """

    return AppResponseDict(
        status="success",
        data={
            "supabaseUrl": request.app.state.settings.supabase_url,
            "supabaseKey": request.app.state.settings.supabase_anon_key,
            "backendUrl": request.url.scheme + "://" + request.url.netloc,
            "isSignUp": False,
            "sentryDsn": request.app.state.settings.sentry_client_dsn or request.app.state.settings.sentry_server_dsn,
            "sentryEnvironment": request.app.state.settings.environment,
            "sentryEnabled": True,
        },
    )


@dev_router.get("/app_state", response_model=None)
async def app_state(request: Request) -> AppResponseDict:
    """
    Returns the app state for dev-admin.
    """
    return AppResponseDict(data=getattr(request.app.state, "_state", {}))


@dev_router.get("/request_state", response_model=None)
async def request_state(request: Request) -> AppResponseDict:
    """
    Returns the request state for dev-admin.
    """
    return AppResponseDict(
        data=getattr(request.state, "_state", {}),
    )


@dev_router.get("/rbac", response_model=None, tags=["public"])
async def rbac_data(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> AppResponseDict:
    """
    Returns the RBAC (Role-Based Access Control) data for dev-admin.
    Shows all router information including routes, tags, and allowed roles.
    """
    try:
        # Get RouterInfo instance from AuthService
        router_info = auth_service.get_router_info()

        # Get all route cache data
        route_cache = router_info._route_cache  # type: ignore[reportPrivateUsage, unused-ignore]

        # Convert RouterItem data to a more frontend-friendly format
        rbac_data = []
        for cache_key, route_item in route_cache.items():
            rbac_entry = {
                "id": cache_key,  # Unique identifier for the table
                "method": route_item["method"],
                "path": route_item["path"],
                "path_template": route_item["path_template"],
                "name": route_item["name"],
                "tags": route_item["tags"],
                "allowed_roles": sorted(route_item["allowed_roles"]),  # Convert set to sorted list for JSON
                "roles_count": len(route_item["allowed_roles"]),
                "tags_count": len(route_item["tags"]),
            }
            rbac_data.append(rbac_entry)

        # Sort by method and path for consistent display
        rbac_data.sort(key=lambda x: (x["method"], x["path"]))

        # Get cache statistics
        cache_stats = {
            "total_routes": len(rbac_data),
            "route_cache_size": router_info.get_route_cache_size(),
            "tag_role_cache_size": router_info.get_tag_role_cache_size(),
        }

        return AppResponseDict(
            status="success",
            message=f"Retrieved {len(rbac_data)} RBAC entries",
            data={
                "rbac_entries": rbac_data,
                "cache_stats": cache_stats,
            },
        )

    except Exception as e:
        logger.error(f"Error retrieving RBAC data: {e}")
        return AppResponseDict(
            status="error",
            message=f"Failed to retrieve RBAC data: {e!s}",
            data={
                "rbac_entries": [],
                "cache_stats": {
                    "total_routes": 0,
                    "route_cache_size": 0,
                    "tag_role_cache_size": 0,
                },
            },
        )


@dev_router.post("/sys_dict/show", response_model=None)
async def show_sys_dict(request: SysDictShowRequest) -> AppResponseDict:
    """
    Show the content in sys_dict by category with optional filters.

    Args:
        request: SysDictShowRequest containing optional filter criteria

    Returns:
        AppResponseDict with sys_dict data
    """
    try:
        sys_service = SysService()
        data = await sys_service.get_sys_dict_with_status(
            category=request.category, key=request.key, value=request.value, in_used_only=request.in_used_only
        )

        # Convert to list format for frontend table display
        items = []
        for item_data in data:
            items.append(
                {
                    "category": item_data["category"],
                    "key": item_data["key"],
                    "value": item_data["value"],
                    "in_used": item_data["in_used"],
                }
            )

        return AppResponseDict(
            status="success", message=f"Retrieved {len(items)} sys_dict entries", data={"items": items}
        )
    except Exception as e:
        logger.error(f"Error retrieving sys_dict data: {e}")
        return AppResponseDict(status="error", message=f"Failed to retrieve sys_dict data: {e!s}", data={"items": []})


@dev_router.post("/sys_dict/adjust", response_model=None)
async def adjust_sys_dict(request: SysDictAdjustRequest) -> AppResponseDict:
    """
    Maintain the content in sys_dict by category (support add, soft delete and update existing items).

    Args:
        request: SysDictAdjustRequest containing category and items to set

    Returns:
        AppResponseDict with operation result
    """
    try:
        sys_service = SysService()

        # Convert items to the format expected by set_sys_dict
        values: dict[int, str] = {}
        for item in request.items:
            if item.in_used:  # Only include active items
                values[item.key] = item.value

        success = await sys_service.set_sys_dict(request.category, values)

        if success:
            return AppResponseDict(
                status="success",
                message=f"Successfully updated sys_dict for category '{request.category}'",
                data={"category": request.category, "items_count": len(values)},
            )
        return AppResponseDict(
            status="error",
            message=f"Failed to update sys_dict for category '{request.category}'",
            data={"category": request.category},
        )
    except Exception as e:
        logger.error(f"Error adjusting sys_dict data: {e}")
        return AppResponseDict(
            status="error",
            message=f"Failed to adjust sys_dict data: {e!s}",
            data={"category": request.category if request else None},
        )


@dev_router.post("/sys_map/show", response_model=None)
async def show_sys_map(request: SysMapShowRequest) -> AppResponseDict:
    """
    Show the content in sys_map by category with optional filters.

    Args:
        request: SysMapShowRequest containing optional filter criteria

    Returns:
        AppResponseDict with sys_map data
    """
    try:
        sys_service = SysService()
        data = await sys_service.get_sys_map_with_status(
            category=request.category,
            left=request.left_value,
            right=request.right_value,
            in_used_only=request.in_used_only,
        )

        # Convert to list format for frontend table display
        items = []
        for item_data in data:
            items.append(
                {
                    "category": item_data["category"],
                    "left_value": item_data["left_value"],
                    "right_value": item_data["right_value"],
                    "in_used": item_data["in_used"],
                }
            )

        return AppResponseDict(
            status="success", message=f"Retrieved {len(items)} sys_map entries", data={"items": items}
        )
    except Exception as e:
        logger.error(f"Error retrieving sys_map data: {e}")
        return AppResponseDict(status="error", message=f"Failed to retrieve sys_map data: {e!s}", data={"items": []})


@dev_router.post("/sys_map/adjust", response_model=None)
async def adjust_sys_map(request: SysMapAdjustRequest) -> AppResponseDict:
    """
    Maintain the content in sys_map by category (support add, soft delete and update existing items).

    Args:
        request: SysMapAdjustRequest containing category and items to set

    Returns:
        AppResponseDict with operation result
    """
    try:
        sys_service = SysService()

        # Convert items to the format expected by set_sys_map
        values: dict[str, list[str]] = {}
        for item in request.items:
            if item.in_used:  # Only include active items
                if item.left_value not in values:
                    values[item.left_value] = []
                values[item.left_value].append(item.right_value)

        success = await sys_service.set_sys_map(request.category, values)

        if success:
            total_items = sum(len(rights) for rights in values.values())
            return AppResponseDict(
                status="success",
                message=f"Successfully updated sys_map for category '{request.category}'",
                data={"category": request.category, "items_count": total_items},
            )
        return AppResponseDict(
            status="error",
            message=f"Failed to update sys_map for category '{request.category}'",
            data={"category": request.category},
        )
    except Exception as e:
        logger.error(f"Error adjusting sys_map data: {e}")
        return AppResponseDict(
            status="error",
            message=f"Failed to adjust sys_map data: {e!s}",
            data={"category": request.category if request else None},
        )


@dev_router.delete("/sys_dict/delete", response_model=None)
async def hard_delete_sys_dict_entry(request: SysDictDeleteRequest) -> AppResponseDict:
    """
    Permanently delete a specific SYS_DICT entry.

    Args:
        request: SysDictDeleteRequest containing category, key, and value

    Returns:
        AppResponseDict with deletion result
    """
    try:
        sys_service = SysService()
        success = await sys_service.hard_delete_sys_dict_entry(request.category, request.key, request.value)

        if success:
            return AppResponseDict(
                status="success",
                message=f"Successfully deleted sys_dict entry: category='{request.category}', key={request.key}, value='{request.value}'",
                data={"category": request.category, "key": request.key, "value": request.value},
            )
        return AppResponseDict(
            status="error",
            message=f"Entry not found or failed to delete: category='{request.category}', key={request.key}, value='{request.value}'",
            data={"category": request.category, "key": request.key, "value": request.value},
        )
    except Exception as e:
        logger.error(f"Error hard deleting sys_dict entry: {e}")
        return AppResponseDict(
            status="error",
            message=f"Failed to hard delete sys_dict entry: {e!s}",
            data={"category": request.category, "key": request.key, "value": request.value},
        )


@dev_router.delete("/sys_map/delete", response_model=None)
async def hard_delete_sys_map_entry(request: SysMapDeleteRequest) -> AppResponseDict:
    """
    Permanently delete a specific SYS_MAP entry.

    Args:
        request: SysMapDeleteRequest containing category, left_value, and right_value

    Returns:
        AppResponseDict with deletion result
    """
    try:
        sys_service = SysService()
        success = await sys_service.hard_delete_sys_map_entry(request.category, request.left_value, request.right_value)

        if success:
            return AppResponseDict(
                status="success",
                message=f"Successfully deleted sys_map entry: category='{request.category}', left='{request.left_value}', right='{request.right_value}'",
                data={
                    "category": request.category,
                    "left_value": request.left_value,
                    "right_value": request.right_value,
                },
            )
        return AppResponseDict(
            status="error",
            message=f"Entry not found or failed to delete: category='{request.category}', left='{request.left_value}', right='{request.right_value}'",
            data={"category": request.category, "left_value": request.left_value, "right_value": request.right_value},
        )
    except Exception as e:
        logger.error(f"Error hard deleting sys_map entry: {e}")
        return AppResponseDict(
            status="error",
            message=f"Failed to hard delete sys_map entry: {e!s}",
            data={"category": request.category, "left_value": request.left_value, "right_value": request.right_value},
        )


@dev_router.get("/client_api_{lib}.{extname}", response_model=None, tags=["public"])
async def generate_client_api(
    lib: Literal["fetch", "axios"],
    extname: Literal["js", "ts"],
    request: Request,
) -> AppResponseDict | Response:
    """
    Generate client API code for the specified library and file extension.

    Args:
        lib: HTTP client library ('fetch' or 'axios')
        extname: File extension ('js' for JavaScript, 'ts' for TypeScript)
        request: FastAPI request object

    Returns:
        Response with generated client code as downloadable file, or AppResponseDict on error
    """
    try:
        # Map extension to language
        language_map: dict[Literal["js", "ts"], Literal["javascript", "typescript"]] = {
            "js": "javascript",
            "ts": "typescript",
        }
        language = language_map[extname]

        # Create client generator
        generator = ClientGenerator()

        # Create configuration with the current request's base URL to avoid CORS issues
        current_base_url = f"{request.url.scheme}://{request.url.netloc}"
        config = ClientConfig(
            language=language,
            http_client=lib,
            class_name="ApiClient",
            base_url=current_base_url,
        )

        # Generate client code from ALL routes (including those excluded from OpenAPI schema)
        client_code = generator.generate_from_app_all_routes(request.app, config)

        # Determine content type - use text/javascript for executable JS files
        content_type = "text/javascript" if extname == "js" else "application/typescript"

        # Headers for tracking, but no Content-Disposition to allow inline execution
        return Response(
            content=client_code,
            media_type=content_type,
            headers={
                "X-Generated-Language": language,
                "X-Generated-Library": lib,
                "Cache-Control": "public, max-age=300",  # 5 minutes cache
            },
        )

    except Exception as e:
        logger.error(f"Error generating client API: {e}")
        return AppResponseDict(
            status="error",
            message=f"Failed to generate client API: {e!s}",
            data={
                "lib": lib,
                "extname": extname,
                "code": None,
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


@sys_router.get("/health", response_model=None, tags=["public"])
async def check_health(request: Request) -> AppResponseDict:
    await check_all_resources(request.app, request.app.state.settings)

    latest_status_check = getattr(request.app.state, "latest_status_check", None)
    latest_status_info = getattr(request.app.state, "latest_status_info", {})

    return AppResponseDict(
        data={
            "latest_status_check": latest_status_check,
            "db": latest_status_info.get("db", {}),
            "redis": latest_status_info.get("redis", {}),
            "sentry": latest_status_info.get("sentry", {}),
            "auth": latest_status_info.get("auth", {}),
        },
    )
