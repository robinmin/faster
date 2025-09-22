from typing import Any
import uuid

from fastapi import Request

from ..logger import get_logger

logger = get_logger(__name__)


def _extract_authorization_header(request: Request | None) -> str | None:
    """Extract and validate Authorization header from request."""
    if request is None:
        logger.info("No request object provided for token extraction")
        return None

    authorization = request.headers.get("Authorization")
    if authorization is None:
        logger.debug("No Authorization header found in request")
        return None

    authorization = authorization.strip()
    return authorization


def _validate_bearer_scheme(authorization: str) -> str | None:
    """Validate Bearer scheme and extract token."""
    if not authorization.lower().startswith("bearer "):
        logger.debug(f"Authorization header does not use Bearer scheme: {authorization[:20]}...")
        return None

    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        logger.debug("Malformed Authorization header: missing token after Bearer")
        return None

    token = parts[1].strip()
    if not token:
        logger.debug("Empty token found after Bearer prefix")
        return None

    return token


def _validate_jwt_structure(token: str | None) -> bool:  # type: ignore[reportUnusedFunction, unused-ignore]
    """Validate JWT token structure and format."""
    if not token:
        return False

    token_parts = token.split(".")
    if len(token_parts) != 3:
        logger.debug(f"Invalid JWT format: expected 3 parts, got {len(token_parts)}")
        return False

    for i, part in enumerate(token_parts):
        if not part or not part.replace("-", "").replace("_", "").isalnum():
            logger.debug(f"Invalid JWT part {i + 1}: contains invalid characters or is empty")
            return False

    return True


def extract_bearer_token_from_request(request: Request) -> str | None:
    """
    Extract Bearer token from HTTP request with comprehensive validation.

    This utility function handles multiple token sources and formats:
    - Authorization header with Bearer scheme
    - Validates token format and structure
    - Handles edge cases and malformed headers
    - Returns clean token string or None if invalid

    Args:
        request: FastAPI Request object containing HTTP headers

    Returns:
        Clean JWT token string (without 'Bearer ' prefix) if valid, None otherwise

    Example:
        # From Authorization header: "Bearer eyJ0eXAiOiJKV1Qi..."
        token = extract_bearer_token_from_request(request)
        # Returns: "eyJ0eXAiOiJKV1Qi..." or None
    """
    try:
        authorization = _extract_authorization_header(request)
        if not authorization:
            return None

        token = _validate_bearer_scheme(authorization)
        if not token:
            return None

        # TODO: Skip JWT structure validation for now to maintain backward compatibility
        if not _validate_jwt_structure(token):
            return None

        # logger.debug("Successfully extracted Bearer token from request")
        return token

    except Exception as e:
        logger.error(f"Unexpected error during token extraction: {e}")
        return None


def extract_token_from_multiple_sources(request: Request | None) -> str | None:
    """
    Extract JWT token from multiple possible sources in order of preference.

    Token sources checked in order:
    1. Authorization header (Bearer scheme) - most common
    2. X-Access-Token header - alternative header
    3. Cookie named 'access_token' - for browser-based apps
    4. Query parameter 'token' - for WebSocket or special cases (least secure)

    Args:
        request: FastAPI Request object

    Returns:
        JWT token string if found from any source, None otherwise

    Security Note:
        Query parameter tokens are logged as least secure option.
        Consider disabling query parameter extraction in production.
    """
    if not request:
        return None

    # Priority 1: Authorization header (Bearer scheme)
    bearer_token = extract_bearer_token_from_request(request)
    if bearer_token:
        return bearer_token

    try:
        # Priority 2: X-Access-Token header (common alternative)
        access_token = request.headers.get("X-Access-Token", "").strip()
        if access_token:  # Skip JWT validation for backward compatibility
            logger.debug("Token extracted from X-Access-Token header")
            return access_token

        # Priority 3: Cookie-based token (for browser apps)
        if hasattr(request, "cookies"):
            cookie_token = request.cookies.get("access_token", "").strip()
            if cookie_token:  # Skip JWT validation for backward compatibility
                logger.debug("Token extracted from access_token cookie")
                return cookie_token

        # Priority 4: Query parameter (least secure, log warning)
        if hasattr(request, "query_params"):
            query_token = request.query_params.get("token", "").strip()
            if query_token:  # Skip JWT validation for backward compatibility
                logger.warning("Token extracted from query parameter - consider more secure method")
                return query_token

    except Exception as e:
        logger.error(f"Error checking alternative token sources: {e}")

    logger.debug("No valid token found from any source")
    return None


def _is_valid_jwt_format(token: str) -> bool:  # type: ignore[reportUnusedFunction, unused-ignore]
    """
    Quick JWT format validation without cryptographic verification.

    Checks:
    - Has exactly 3 parts separated by dots
    - Each part contains valid base64url characters
    - No part is empty

    Args:
        token: Token string to validate

    Returns:
        True if token has valid JWT structure, False otherwise
    """
    if not token:
        return False

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return False

        # Check each part has valid base64url characters
        for part in parts:
            if not part:
                return False
            # Base64url uses: A-Z, a-z, 0-9, -, _
            if not all(c.isalnum() or c in "-_" for c in part):
                return False

        return True
    except Exception:
        return False


# =============================================================================
# Password Validation Utilities
# =============================================================================


def validate_password_strength(password: str | None) -> tuple[bool, list[str]]:
    """
    Validate password strength according to security requirements.

    Args:
        password: Password string to validate

    Returns:
        Tuple of (is_valid, error_messages)
        - is_valid: True if password meets all requirements
        - error_messages: List of validation error messages

    Requirements:
        - At least 8 characters long
        - Contains at least one uppercase letter
        - Contains at least one lowercase letter
        - Contains at least one digit
        - Contains at least one special character
    """
    errors: list[str] = []

    if not password:
        errors.append("Password cannot be empty")
        return False, errors

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")

    if not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")

    if not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")

    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit")

    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in password):
        errors.append("Password must contain at least one special character")

    return len(errors) == 0, errors


def sanitize_email(email: str | None) -> str | None:
    """
    Sanitize and validate email address.

    Args:
        email: Email address to sanitize

    Returns:
        Sanitized email address if valid, None otherwise
    """
    if not email:
        return None

    # Basic sanitization
    email = email.strip().lower()

    # Basic email validation (simplified)
    if "@" not in email or "." not in email:
        return None

    # Check for basic email format
    parts = email.split("@")
    if len(parts) != 2:
        return None

    local_part, domain_part = parts
    if not local_part or not domain_part:
        return None

    # Check domain has at least one dot
    if "." not in domain_part:
        return None

    return email


# =============================================================================
# User Data Validation Utilities
# =============================================================================


def validate_user_id(user_id: str | None) -> bool:
    """
    Validate user ID format and content.

    Args:
        user_id: User ID to validate

    Returns:
        True if user ID is valid, False otherwise
    """
    if not user_id:
        return False

    user_id = user_id.strip()

    # Check minimum length
    if len(user_id) < 3:
        return False

    # Check maximum length (reasonable limit)
    if len(user_id) > 255:
        return False

    # Allow alphanumeric characters, hyphens, and underscores
    return all(c.isalnum() or c in "-_" for c in user_id)


def validate_role_name(role: str | None) -> bool:
    """
    Validate role name format and content.

    Args:
        role: Role name to validate

    Returns:
        True if role name is valid, False otherwise
    """
    if not role:
        return False

    role = role.strip()

    # Check minimum length
    if len(role) < 2:
        return False

    # Check maximum length
    if len(role) > 50:
        return False

    # Allow alphanumeric characters, hyphens, and underscores
    return all(c.isalnum() or c in "-_" for c in role)


# =============================================================================
# Security Utilities
# =============================================================================


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data for logging purposes.

    Args:
        data: Sensitive data to mask
        visible_chars: Number of characters to keep visible at the end

    Returns:
        Masked string with only last few characters visible
    """
    if not data:
        return ""

    if len(data) <= visible_chars:
        return "*" * len(data)

    masked_length = len(data) - visible_chars
    return "*" * masked_length + data[-visible_chars:]


def generate_trace_id() -> str:
    """
    Generate a unique trace ID for request tracking.

    Returns:
        Unique trace ID string
    """
    return str(uuid.uuid4())


# =============================================================================
# Event Logging Utilities
# =============================================================================


async def log_event(
    request: Request | None = None,
    event_type: str = "",
    event_name: str = "",
    event_source: str = "",
    user_auth_id: str | None = None,
    trace_id: str | None = None,
    session_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    client_info: str | None = None,
    referrer: str | None = None,
    country_code: str | None = None,
    city: str | None = None,
    timezone: str | None = None,
    event_payload: dict[str, Any] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> bool:
    """
    Log a user action/event to the AUTH_USER_ACTION table with automatic field extraction.

    This utility function automatically extracts common fields from the request object
    when not explicitly provided, providing sensible defaults for audit logging.

    Args:
        request: FastAPI Request object for automatic field extraction
        event_type: Type of event (e.g., 'user', 'admin', 'auth')
        event_name: Specific event name (e.g., 'login', 'profile_update')
        event_source: Source of the event (e.g., 'user_action', 'admin_action')
        user_auth_id: User authentication ID (auto-extracted if request provided)
        trace_id: Request trace ID (auto-extracted from X-Request-ID header)
        session_id: Session identifier (defaults to user_auth_id for grouping)
        ip_address: Client IP address (auto-extracted from request)
        user_agent: User agent string (auto-extracted from request headers)
        client_info: Additional client information
        referrer: HTTP referrer header
        country_code: Client country code
        city: Client city
        timezone: Client timezone
        event_payload: Structured event data
        extra_metadata: Additional metadata (auto-includes request method/URL)

    Returns:
        True if logging successful, False otherwise
    """
    from .services import AuthService  # noqa: PLC0415  # Import here to avoid circular imports

    return await AuthService.get_instance().log_event_raw(
        event_type=event_type,
        event_name=event_name,
        event_source=event_source,
        user_auth_id=user_auth_id,
        trace_id=trace_id,
        session_id=session_id,
        ip_address=ip_address,
        user_agent=user_agent,
        client_info=client_info,
        referrer=referrer,
        country_code=country_code,
        city=city,
        timezone=timezone,
        event_payload=event_payload,
        extra_metadata=extra_metadata,
        request=request,
    )
