from typing import Any

from fastapi import status


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
