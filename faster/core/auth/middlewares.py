from typing import cast

from fastapi import Request, status
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from ..exceptions import AuthError
from ..logger import get_logger
from ..models import AppResponseDict
from ..redisex import blacklist_exists
from .models import UserProfileData
from .services import AuthService
from .utilities import extract_bearer_token_from_request

logger = get_logger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, allowed_paths: list[str] | None = None, require_auth: bool = True) -> None:
        """
        Initialize middleware with configuration.
        Args:
            app: FastAPI application instance
            allowed_paths: List of paths to allowed paths from authentication
            require_auth: Whether to require authentication for non-allowed paths
        """
        super().__init__(app)
        self._auth_service = AuthService.get_instance()

        # Process allowed paths for optimal performance
        raw_paths = allowed_paths or ["/docs", "/redoc", "/openapi.json", "/health"]
        self._exact_allowed_paths = set[str]()
        self._prefix_allowed_paths = list[str]()

        for path in raw_paths:
            if path.endswith("/*"):
                # Prefix pattern: "/api/public/*" -> "/api/public"
                self._prefix_allowed_paths.append(path[:-2])
            else:
                # Exact match
                self._exact_allowed_paths.add(path)

        self._require_auth = require_auth
        self._security = HTTPBearer(auto_error=False)

    def _check_allowed_path(self, request: Request, current_path: str) -> bool:
        """Check if the request path is allowed and set appropriate state."""
        # Fast O(1) exact match check first
        if current_path in self._exact_allowed_paths:
            self._set_unauthenticated_state(request)
            logger.debug(f"[auth] Allowed path: {current_path}")
            return True

        # Only check prefixes if needed - O(n) but typically small n
        if any(current_path.startswith(prefix) for prefix in self._prefix_allowed_paths):
            self._set_unauthenticated_state(request)
            logger.debug(f"[auth] Allowed path: {current_path}")
            return True

        return False

    async def _get_authenticated_user_profile(self, user_id: str) -> UserProfileData | None:
        """Retrieve and validate user profile from auth service."""
        try:
            user_profile = await self._auth_service.get_user_by_id(user_id, from_cache=True)
            if user_profile:
                return user_profile

            # Token valid but user not found
            logger.warning(f"[auth] Valid token but user profile not found: {user_id}")
            return None

        except Exception as e:
            # Error fetching user profile
            logger.error(f"[auth] Error fetching user profile: {e}")
            return None

    async def _set_authenticated_state(self, request: Request, user_profile: UserProfileData) -> None:
        """Set request state for successfully authenticated user."""
        request.state.user = user_profile
        request.state.authenticated = True
        request.state.roles = set(await self._auth_service.get_roles(user_profile.id))

    def _set_unauthenticated_state(self, request: Request) -> None:
        """Set request state for unauthenticated request."""
        request.state.user = None
        request.state.authenticated = False
        request.state.roles = set()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response | AppResponseDict:  # noqa: C901
        """
        The core of the authentication middleware,to process authentication for incoming requests. The basic logic is
        to extract token from request, authenticate it and set user profile in request state.

        For public endpoints, the middleware will allow access without authentication.
        For the other endpoints, the middleware will authenticate the request and set user profile in request state.
        State change:
            - request.state.user: Set user profile in request state.
            - request.state.authenticated: Set authenticated flag in request state.
        """
        current_path = request.url.path
        current_method = request.method

        try:
            # 1. Check if authentication is enabled - if not, bypass all auth checks
            if not self._require_auth or current_method in ["HEAD", "OPTIONS"]:
                self._set_unauthenticated_state(request)
                return await call_next(request)

            # 2. Convert request path to its original path when declared
            route_info = self._auth_service.find_route(current_method, current_path)
            if route_info and route_info["path_template"]:
                current_path = route_info["path_template"]
            else:
                raise AuthError("Route not found", status.HTTP_404_NOT_FOUND)

            # 3. Check allowed paths & update request.state
            if self._check_allowed_path(request, current_path):
                return await call_next(request)

            # 4. Get endpoint tags
            if not route_info["tags"]:
                raise AuthError("Endpoint tags not found", status.HTTP_404_NOT_FOUND)

            # 5. Skip public endpoints
            if "public" in route_info["tags"]:
                self._set_unauthenticated_state(request)
                logger.debug(f"[auth] Skipping public endpoint: {current_path}")
                return await call_next(request)

            # 6. Authenticate request and get user profile
            token = extract_bearer_token_from_request(request)
            if not token or await blacklist_exists(token):
                raise AuthError("Invalid token or already logged out")

            # 7. Get user profile
            user_id = await self._auth_service.get_user_id_from_token(token)
            if not user_id:
                self._set_unauthenticated_state(request)
                raise AuthError("User ID required for authentication")

            # 8. Check authentication and authorization
            user_profile = await self._get_authenticated_user_profile(user_id)
            if not user_profile:
                self._set_unauthenticated_state(request)
                raise AuthError("Valid user ID required for authentication")

            # 9. Cache authentication data
            await self._set_authenticated_state(request, user_profile)

            # 10. RBAC check
            if not await self._auth_service.check_access(request.state.roles, route_info["allowed_roles"]):
                raise AuthError("Permission denied by RBAC", status.HTTP_403_FORBIDDEN)
            logger.debug(f"[auth] => pass on {current_method} {current_path} for {user_id}")

            # 11. Continue to the next middleware/endpoint
            return await call_next(request)
        except AuthError as exp:
            logger.error(f"[auth] Authentication error: {exp}")
            return AppResponseDict(
                status="auth error",
                message=exp.message,
                status_code=exp.status_code,
            )
        except Exception as exp:
            logger.error(f"[auth] Unknown Authentication error: {exp}")
            return AppResponseDict(
                status="http error",
                message="Authentication failed",
                status_code=status.HTTP_401_UNAUTHORIZED,
                headers={"WWW-Authenticate": "Bearer"},
            )


async def get_current_user(request: Request) -> UserProfileData | None:
    """Dependency to get current authenticated user."""
    if not hasattr(request.state, "authenticated") or not request.state.authenticated:
        logger.error("Authentication required in get_current_user")
        return None

    return cast(UserProfileData, request.state.user)


async def has_role(request: Request, role: str) -> bool:
    """Check if current user has a specific role."""
    if not hasattr(request.state, "authenticated") or not request.state.authenticated:
        logger.error("Authentication required in has_role")
        return False

    return hasattr(request.state, "roles") and role in request.state.roles
