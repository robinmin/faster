"""Custom exception classes for the auth module."""


class AuthError(Exception):
    """Base class for authentication-related errors."""

    def __init__(self, message: str = "Authentication error occurred."):
        self.message = message
        super().__init__(self.message)


class InvalidCredentialsError(AuthError):
    """Raised when authentication fails due to invalid credentials."""

    def __init__(self, message: str = "Invalid username or password."):
        super().__init__(message)


class UserAlreadyExistsError(AuthError):
    """Raised when trying to register a user that already exists."""

    def __init__(self, message: str = "User with this email already exists."):
        super().__init__(message)


class UserNotFoundError(AuthError):
    """Raised when a user is not found."""

    def __init__(self, message: str = "User not found."):
        super().__init__(message)


class UnverifiedUserError(AuthError):
    """Raised when an unverified user tries to perform a protected action."""

    def __init__(self, message: str = "User account is not verified. Please check your email."):
        super().__init__(message)


class TokenExpiredError(AuthError):
    """Raised when a token has expired."""

    def __init__(self, message: str = "Token has expired."):
        super().__init__(message)


class InvalidTokenError(AuthError):
    """Raised when a token is invalid."""

    def __init__(self, message: str = "Token is invalid or malformed."):
        super().__init__(message)
