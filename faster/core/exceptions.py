from collections import defaultdict
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPError

from faster.core.schemas import APIResponse


class APIError(Exception):
    """Base class for all application exceptions."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors or []


class HTTPError(APIError):
    """Custom HTTP exception class."""

    def __init__(self, message: str, status_code: int, errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message, status_code, errors)


class ValidationError(APIError):
    """Custom validation exception class."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__("Validation error", status_code=422, errors=errors)


async def api_exception_handler(_: Request, exc: APIError) -> APIResponse[Any]:
    """Global exception handler for APIError."""
    return APIResponse(
        status="error",
        message=exc.message,
        status_code=exc.status_code,
        data=exc.errors if exc.errors else None,
    )


async def http_exception_handler(_: Request, exc: StarletteHTTPError) -> APIResponse[Any]:
    """Global exception handler for Starlette/FastAPI HTTPException."""
    return APIResponse(
        status="http error",
        message=exc.detail,
        status_code=exc.status_code,
    )


async def custom_validation_exception_handler(_: Request, exc: RequestValidationError) -> APIResponse[Any]:
    """
    Custom global exception handler for Pydantic's RequestValidationError.
    This handler formats the validation errors to be more developer-friendly.
    """
    error_details = defaultdict(list)
    for error in exc.errors():
        field = ".".join(map(str, error["loc"])) if error["loc"] else "general"
        error_details[field].append(error["msg"])

    return APIResponse(
        status="validation error",
        message="Request validation failed",
        status_code=422,
        data=[{"field": k, "messages": v} for k, v in error_details.items()],
    )


class DBError(APIError):
    """Custom DB exception for uniform error handling."""


async def db_exception_handler(request: Request, exp: DBError) -> APIResponse[Any]:
    """Global exception handler for DBError."""
    return APIResponse(
        status="db error",
        message=exp.message,
        status_code=exp.status_code,
        data=exp.errors if exp.errors else None,
    )


class AuthError(APIError):
    """Custom DB exception for authorization error."""


async def auth_exception_handler(request: Request, exp: DBError) -> APIResponse[Any]:
    """Global exception handler for DBError."""
    return APIResponse(
        status="Authentication failed",
        message=exp.message,
        status_code=exp.status_code,
        data=exp.errors if exp.errors else None,
    )
