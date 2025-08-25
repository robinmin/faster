import logging
from typing import cast

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from faster.core.utilities import get_current_endpoint

from .schemas import AuthUser
from .services import AuthService

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, auth_service: AuthService) -> None:
        super().__init__(app)
        self.auth_service = auth_service

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        current_path = request.url.path
        current_endpoint = get_current_endpoint(request, request.app.state.endpoints)
        if not current_endpoint:
            logger.error(f"[auth] Not Found - 404: {current_path}")
            return JSONResponse(
                {"status": "http error", "message": "Not Found"},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        tags = current_endpoint["tags"]
        # logger.debug(f"[auth] {current_endpoint} - {tags}")

        # Skip public endpoints
        if "public" in tags:
            logger.debug(f"[auth] Skipping public endpoint : {current_path}")
            return await call_next(request)

        # Extract JWT
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.error(f"[auth] Not authenticated - 401: {current_path}")
            return JSONResponse(
                {"status": "http error", "message": "Not authenticated"},
                status_code=401,
            )
        token = auth_header.split(" ")[1]

        # Verify JWT
        try:
            payload = self.auth_service.verify_jwt(token)
        except Exception as e:
            logger.error(f"[auth] Invalid token: {e} - 401: {current_path}")
            return JSONResponse({"detail": f"Invalid token: {e}"}, status_code=401)

        user_id = payload["sub"]

        # RBAC check
        allowed = await self.auth_service.check_access(user_id, tags)
        if not allowed:
            logger.debug(f"[auth] Forbidden - 403: {current_path} to user {user_id}")
            return JSONResponse({"detail": "Forbidden: insufficient role"}, status_code=403)

        # Attach auth info to request.state
        email = payload.get("email")
        if not isinstance(email, str):
            email = ""  # Should not happen with valid JWTs

        request.state.auth_user = AuthUser(
            id=user_id,
            email=email,
            token=token,
            raw=payload,
        )
        logger.debug(f"[auth] Authenticated: {current_path} to user {user_id}")

        return await call_next(request)


def get_auth_user(request: Request) -> AuthUser:
    user = cast(AuthUser | None, getattr(request.state, "auth_user", None))
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user
