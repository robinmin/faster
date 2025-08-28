from collections import defaultdict
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError

from .logger import get_logger
from .schemas import AppResponse
from .sentry import capture_it

logger = get_logger(__name__)


###############################################################################
## Define all exception classes
###############################################################################
class AppError(Exception):
    """Base class for all application exceptions."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors or []


class HTTPError(AppError):
    """Custom HTTP exception class."""

    def __init__(self, message: str, status_code: int, errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message, status_code, errors)


class ValidationError(AppError):
    """Custom validation exception class."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__("Validation error", status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, errors=errors)


class DBError(AppError):
    """Custom DB exception for uniform error handling."""


class AuthError(AppError):
    """Custom DB exception for authorization error."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_401_UNAUTHORIZED,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message, status_code, errors)


###############################################################################
##  Define all exception  handlers
###############################################################################
async def app_exception_handler(_: Request, exc: AppError) -> AppResponse[Any]:
    """Global exception handler for APIError."""
    ## report to Sentry
    await capture_it(f"Business logic issue: {exc.message}")

    return AppResponse(
        status="error",
        message=exc.message,
        status_code=exc.status_code,
        data=exc.errors if exc.errors else None,
    )


async def custom_validation_exception_handler(_: Request, exc: RequestValidationError) -> AppResponse[Any]:
    """
    Custom global exception handler for Pydantic's RequestValidationError.
    This handler formats the validation errors to be more developer-friendly.
    """
    error_details = defaultdict(list)
    for error in exc.errors():
        field = ".".join(map(str, error["loc"])) if error["loc"] else "general"
        error_details[field].append(error["msg"])
    logger.error("Validation error: %s", error_details)
    return AppResponse(
        status="validation error",
        message="Request validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        data=[{"field": k, "messages": v} for k, v in error_details.items()],
    )


async def auth_exception_handler(request: Request, exp: AuthError) -> AppResponse[Any]:
    """Global exception handler for AuthError."""
    logger.error("Authentication error: [%d] %s - %s", exp.status_code, exp.message, exp.errors if exp.errors else None)
    return AppResponse(
        status="Authentication failed",
        message=exp.message,
        status_code=exp.status_code,
        data=exp.errors if exp.errors else None,
    )
