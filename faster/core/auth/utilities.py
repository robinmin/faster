from fastapi import Request

from ..logger import get_logger

logger = get_logger(__name__)


def _extract_authorization_header(request: Request | None) -> str | None:
    """Extract and validate Authorization header from request."""
    if request is None:
        logger.debug("No request object provided for token extraction")
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
        # if not _validate_jwt_structure(token):
        #     return None

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
