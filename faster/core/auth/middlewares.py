from typing import cast

from fastapi import Request, status
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from ..logger import get_logger
from ..models import AppResponseDict
from ..redisex import blacklist_exists
from ..utilities import get_current_endpoint
from .models import UserProfileData
from .services import AuthService
from .utilities import extract_bearer_token_from_request

logger = get_logger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app: ASGIApp, auth_service: AuthService, allowed_paths: list[str] | None = None, require_auth: bool = True
    ) -> None:
        """
        Initialize middleware with auth_service and configuration.
        Args:
            app: FastAPI application instance
            auth_service: AuthService instance
            allowed_paths: List of paths to allowed paths from authentication
            require_auth: Whether to require authentication for non-allowed paths
        """
        super().__init__(app)
        self._auth_service = auth_service

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

    def _is_allowed_path(self, path: str) -> bool:
        """Check if the request path is allowed from authentication."""
        # Fast O(1) exact match check first
        if path in self._exact_allowed_paths:
            return True

        # Only check prefixes if needed - O(n) but typically small n
        return any(path.startswith(prefix) for prefix in self._prefix_allowed_paths)

    def _handle_allowed_path(self, request: Request, current_path: str) -> bool:
        """Handle allowed paths in debug mode."""
        if self._is_allowed_path(current_path):
            request.state.user = None
            request.state.authenticated = False
            logger.debug(f"[auth] Allowed path: {current_path}")
            return True
        return False

    def _get_endpoint_tags(self, request: Request, current_path: str) -> list[str] | None:
        """Get endpoint tags or return None if endpoint not found."""
        current_endpoint = get_current_endpoint(request, request.app.state.endpoints)
        if not current_endpoint or "tags" not in current_endpoint:
            logger.error(f"[auth] Not Found - 404: [{request.method.upper()}] {current_path}")
            return None
        return list(current_endpoint["tags"])

    def _is_public_endpoint(self, tags: list[str], current_path: str) -> bool:
        """Check if endpoint is public."""
        if "public" in tags:
            logger.debug(f"[auth] Skipping public endpoint : {current_path}")
            return True
        return False

    async def _set_request_state(self, request: Request, user_id: str | None, current_path: str) -> None:
        """Set request state based on authentication result."""
        if user_id:
            # Successfully authenticated - get full user profile
            try:
                user_profile = await self._auth_service.get_user_by_id(user_id, from_cache=True)
                if user_profile:
                    # User profile is already UserProfileData, no conversion needed
                    request.state.user = user_profile
                    request.state.authenticated = True
                    # TODO: for test purpose to assign role, should be fix after debugging
                    # request.state.roles = set(await self._auth_service.get_roles(user_id))
                    request.state.roles = set("developer")

                    # logger.debug(f"[auth] Successfully authenticated user: {user_id}")
                    return

                # Token valid but user not found - treat as authentication failure
                logger.warning(f"[auth] Valid token but user profile not found: {user_id}")
            except Exception as e:
                # Error fetching user profile - treat as authentication failure
                logger.error(f"[auth] Error fetching user profile: {e}")

        # Authentication failed or no token provided
        request.state.user = None
        request.state.roles = set()
        request.state.authenticated = False
        logger.info(f"[auth] Authentication failed for endpoint: {current_path}")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response | AppResponseDict:  # noqa: PLR0911
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
        try:
            # 1. Handle allowed paths in debug mode
            if self._handle_allowed_path(request, current_path):
                return await call_next(request)

            # 2. Get endpoint tags
            tags = self._get_endpoint_tags(request, current_path)
            if tags is None:
                return AppResponseDict(
                    status="http error",
                    message="Not Found",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            # 3. Skip public endpoints
            if self._is_public_endpoint(tags, current_path):
                return await call_next(request)

            # 4. Authenticate request and get user profile
            token = extract_bearer_token_from_request(request)
            if not token or await blacklist_exists(token):
                return AppResponseDict(
                    status="http error",
                    message="Invalid token or already logged out",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                )

            user_id = await self._auth_service.get_user_id_from_token(token)
            await self._set_request_state(request, user_id, current_path)

            # 5. Check authentication and authorization
            if not user_id and self._require_auth:
                return AppResponseDict(
                    status="http error",
                    message="Authentication required",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                )
            # 6. RBAC check
            if user_id and not await self._auth_service.check_access(user_id, tags):
                return AppResponseDict(
                    status="http error",
                    message="Permission denied",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

            # 7. Continue to the next middleware/endpoint
            response = await call_next(request)
            return response
        except Exception as exp:
            logger.error(f"[auth] Authentication error: {exp}")
            return AppResponseDict(
                status="http error",
                message="Authentication failed",
                status_code=status.HTTP_401_UNAUTHORIZED,
                headers={"WWW-Authenticate": "Bearer"},
            )


async def get_current_user(request: Request) -> UserProfileData | None:
    """Dependency to get current authenticated user."""
    if not hasattr(request.state, "authenticated") or not request.state.authenticated:
        logger.error("Authentication required")
        return None

    return cast(UserProfileData, request.state.user)
