from typing import cast

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp
from supabase_auth.types import User as UserProfile

from faster.core.exceptions import AuthError
from faster.core.logger import get_logger
from faster.core.schemas import AppResponse
from faster.core.utilities import get_current_endpoint

from .schemas import AuthUser
from .services import AuthService

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
        self._exact_allowed_paths = set()
        self._prefix_allowed_paths = []

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

    async def _extract_token_from_request(self, request: Request) -> str | None:
        """Extract Bearer token from request headers."""
        authorization = request.headers.get("Authorization", "")

        if authorization.startswith("Bearer "):
            return authorization.split(" ", 1)[1]

        return None

    async def _authenticate_request(self, request: Request) -> UserProfile | None:
        """Authenticate the request and return user profile if valid."""
        token = await self._extract_token_from_request(request)

        if not token:
            return None

        try:
            user_profile = await self._auth_service.authenticate_token(token)
            return user_profile
        except AuthError:
            logger.warning("Authentication failed for token")
            return None

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process authentication for incoming requests."""
        current_path = request.url.path
        try:
            # 1, Allow default paths in debug mode
            if self._is_allowed_path(current_path):
                request.state.user = None
                request.state.authenticated = False
                logger.debug(f"[auth] Allowed path: {current_path}")
                return await call_next(request)

            # 2, Find endpoints and tags
            current_endpoint = get_current_endpoint(request, request.app.state.endpoints)
            if not current_endpoint or "tags" not in current_endpoint:
                logger.error(f"[auth] Not Found - 404: {current_path}")
                return AppResponse(
                    status="http error",
                    message="Not Found",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            tags = current_endpoint["tags"]

            # 3, Skip public endpoints
            if "public" in tags:
                logger.debug(f"[auth] Skipping public endpoint : {current_path}")
                return await call_next(request)

            # 4, Attempt to authenticate the request
            user_profile = await self._authenticate_request(request)
            if user_profile:
                # Successfully authenticated
                request.state.user = user_profile
                request.state.authenticated = True
            else:
                # Authentication failed
                request.state.user = None
                request.state.authenticated = False

                # If authentication is required and failed, return 401
                if self._require_auth:
                    return AppResponse(
                        status="http error",
                        message="Authentication required",
                        status_code=status.HTTP_401_UNAUTHORIZED,
                    )

            # 5, Continue to the next middleware/endpoint
            response = await call_next(request)
            return response
        except Exception as exp:
            logger.error(f"[auth] Authentication error: {exp}")
            return AppResponse(
                status="http error",
                message="Authentication failed",
                status_code=status.HTTP_401_UNAUTHORIZED,
                headers={"WWW-Authenticate": "Bearer"},
            )


def get_auth_user(request: Request) -> AuthUser:
    user = cast(AuthUser | None, getattr(request.state, "auth_user", None))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user
