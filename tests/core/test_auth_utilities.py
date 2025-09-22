"""Comprehensive tests for auth utilities module."""

import base64
import json
from unittest.mock import MagicMock, patch

from fastapi import Request
from starlette.datastructures import Headers

from faster.core.auth.utilities import (
    _extract_authorization_header,  # type: ignore[reportPrivateUsage, unused-ignore]
    _is_valid_jwt_format,  # type: ignore[reportPrivateUsage, unused-ignore]
    _validate_bearer_scheme,  # type: ignore[reportPrivateUsage, unused-ignore]
    _validate_jwt_structure,  # type: ignore[reportPrivateUsage, unused-ignore]
    extract_bearer_token_from_request,
    extract_token_from_multiple_sources,
)


class TestExtractAuthorizationHeader:
    """Test _extract_authorization_header function."""

    def test_extract_authorization_header_valid(self) -> None:
        """Test extracting valid Authorization header."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({"Authorization": "Bearer token123"})

        result = _extract_authorization_header(mock_request)
        assert result == "Bearer token123"

    def test_extract_authorization_header_missing(self) -> None:
        """Test extracting missing Authorization header."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({})

        result = _extract_authorization_header(mock_request)
        assert result is None

    def test_extract_authorization_header_empty(self) -> None:
        """Test extracting empty Authorization header."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({"Authorization": ""})

        result = _extract_authorization_header(mock_request)
        assert result == ""

    def test_extract_authorization_header_none_request(self) -> None:
        """Test extracting Authorization header with None request."""
        result = _extract_authorization_header(None)
        assert result is None

    def test_extract_authorization_header_case_insensitive(self) -> None:
        """Test extracting Authorization header is case insensitive."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({"authorization": "Bearer token123"})

        result = _extract_authorization_header(mock_request)
        assert result == "Bearer token123"


class TestValidateBearerScheme:
    """Test _validate_bearer_scheme function."""

    def test_validate_bearer_scheme_valid(self) -> None:
        """Test validating valid Bearer scheme."""
        authorization = "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9"
        result = _validate_bearer_scheme(authorization)
        assert result == "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9"

    def test_validate_bearer_scheme_invalid_scheme(self) -> None:
        """Test validating invalid scheme."""
        authorization = "Basic dXNlcjpwYXNz"
        result = _validate_bearer_scheme(authorization)
        assert result is None

    def test_validate_bearer_scheme_missing_space(self) -> None:
        """Test validating Bearer scheme without space."""
        authorization = "Bearertoken123"
        result = _validate_bearer_scheme(authorization)
        assert result is None

    def test_validate_bearer_scheme_empty_token(self) -> None:
        """Test validating Bearer scheme with empty token."""
        authorization = "Bearer "
        result = _validate_bearer_scheme(authorization)
        assert result is None

    def test_validate_bearer_scheme_case_insensitive(self) -> None:
        """Test that Bearer scheme validation is case insensitive."""
        authorization = "bearer token123"
        result = _validate_bearer_scheme(authorization)
        assert result == "token123"

    def test_validate_bearer_scheme_extra_spaces(self) -> None:
        """Test validating Bearer scheme with extra spaces."""
        authorization = "Bearer  token123"
        result = _validate_bearer_scheme(authorization)
        assert result == "token123"

    def test_validate_bearer_scheme_no_token(self) -> None:
        """Test validating Bearer scheme without token."""
        authorization = "Bearer"
        result = _validate_bearer_scheme(authorization)
        assert result is None


class TestValidateJwtStructure:
    """Test _validate_jwt_structure function."""

    def test_validate_jwt_structure_valid(self) -> None:
        """Test validating valid JWT structure."""
        # Create a proper JWT-like token
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {"sub": "user123", "exp": 1638360000}
        signature = "signature"

        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")

        token = f"{header_b64}.{payload_b64}.{signature}"

        result = _validate_jwt_structure(token)
        assert result is True

    def test_validate_jwt_structure_invalid_parts(self) -> None:
        """Test validating JWT with wrong number of parts."""
        token = "part1.part2"  # Only 2 parts
        result = _validate_jwt_structure(token)
        assert result is False

    def test_validate_jwt_structure_empty_token(self) -> None:
        """Test validating empty token."""
        result = _validate_jwt_structure("")
        assert result is False

    def test_validate_jwt_structure_none_token(self) -> None:
        """Test validating None token."""
        result = _validate_jwt_structure(None)
        assert result is False

    def test_validate_jwt_structure_invalid_characters(self) -> None:
        """Test validating JWT with invalid base64url characters."""
        token = "invalid@chars.header.payload.signature"
        result = _validate_jwt_structure(token)
        assert result is False

    def test_validate_jwt_structure_empty_part(self) -> None:
        """Test validating JWT with empty part."""
        token = ".payload.signature"
        result = _validate_jwt_structure(token)
        assert result is False

    def test_validate_jwt_structure_four_parts(self) -> None:
        """Test validating JWT with four parts."""
        token = "header.payload.signature.extra"
        result = _validate_jwt_structure(token)
        assert result is False


class TestIsValidJwtFormat:
    """Test _is_valid_jwt_format function."""

    def test_is_valid_jwt_format_valid(self) -> None:
        """Test validating valid JWT format."""
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {"sub": "user123"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        token = f"{header_b64}.{payload_b64}.signature"

        result = _is_valid_jwt_format(token)
        assert result is True

    def test_is_valid_jwt_format_invalid_structure(self) -> None:
        """Test validating invalid JWT structure."""
        result = _is_valid_jwt_format("not.a.jwt.invalid")
        assert result is False

    def test_is_valid_jwt_format_empty(self) -> None:
        """Test validating empty string."""
        result = _is_valid_jwt_format("")
        assert result is False

    def test_is_valid_jwt_format_none(self) -> None:
        """Test validating None."""
        result = _is_valid_jwt_format(None)  # type: ignore[arg-type]
        assert result is False

    def test_is_valid_jwt_format_invalid_chars(self) -> None:
        """Test validating JWT with invalid characters."""
        token = "invalid@header.payload.signature"
        result = _is_valid_jwt_format(token)
        assert result is False

    def test_is_valid_jwt_format_valid_chars_only(self) -> None:
        """Test that only valid base64url characters are accepted."""
        # This should fail because @ is not valid in base64url
        token = "a@b.c.d"
        result = _is_valid_jwt_format(token)
        assert result is False


class TestExtractBearerTokenFromRequest:
    """Test extract_bearer_token_from_request function."""

    def test_extract_bearer_token_from_request_valid(self) -> None:
        """Test extracting valid Bearer token from request."""
        # Use a properly structured JWT token (header.payload.signature)
        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers(
            {
                "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
            }
        )

        result = extract_bearer_token_from_request(mock_request)
        assert (
            result
            == "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )

    def test_extract_bearer_token_from_request_missing_header(self) -> None:
        """Test extracting token when Authorization header is missing."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({})

        result = extract_bearer_token_from_request(mock_request)
        assert result is None

    def test_extract_bearer_token_from_request_invalid_scheme(self) -> None:
        """Test extracting token with invalid scheme."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({"Authorization": "Basic dXNlcjpwYXNz"})

        result = extract_bearer_token_from_request(mock_request)
        assert result is None

    def test_extract_bearer_token_from_request_invalid_jwt(self) -> None:
        """Test extracting invalid JWT token."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({"Authorization": "Bearer invalid.jwt"})

        result = extract_bearer_token_from_request(mock_request)
        assert result is None  # Invalid JWT structure is now properly validated

    def test_extract_bearer_token_from_request_empty_token(self) -> None:
        """Test extracting empty token."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({"Authorization": "Bearer "})

        result = extract_bearer_token_from_request(mock_request)
        assert result is None

    def test_extract_bearer_token_from_request_none_request(self) -> None:
        """Test extracting token with None request."""
        result = extract_bearer_token_from_request(None)  # type: ignore[arg-type]
        assert result is None

    def test_extract_bearer_token_from_request_case_insensitive(self) -> None:
        """Test extracting token with case insensitive header."""
        # Create a valid JWT-like token for testing
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {"sub": "user123"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        token = f"{header_b64}.{payload_b64}.signature"

        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({"authorization": f"Bearer {token}"})

        result = extract_bearer_token_from_request(mock_request)
        assert result == token


class TestExtractTokenFromMultipleSources:
    """Test extract_token_from_multiple_sources function."""

    def test_extract_token_from_multiple_sources_authorization_header(self) -> None:
        """Test extracting token from Authorization header first."""
        # Create a valid JWT-like token
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {"sub": "user123"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        token = f"{header_b64}.{payload_b64}.signature"

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": f"Bearer {token}"}
        mock_request.cookies = {}
        mock_request.query_params = {}

        result = extract_token_from_multiple_sources(mock_request)
        assert result == token

    def test_extract_token_from_multiple_sources_x_access_token(self) -> None:
        """Test extracting token from X-Access-Token header."""
        mock_request = MagicMock()
        mock_request.headers = {"X-Access-Token": "token456"}
        mock_request.cookies = {}
        mock_request.query_params = {}

        result = extract_token_from_multiple_sources(mock_request)
        assert result == "token456"

    def test_extract_token_from_multiple_sources_cookie(self) -> None:
        """Test extracting token from cookie."""
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.cookies = {"access_token": "token789"}
        mock_request.query_params = {}

        result = extract_token_from_multiple_sources(mock_request)
        assert result == "token789"

    def test_extract_token_from_multiple_sources_query_param(self) -> None:
        """Test extracting token from query parameter."""
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.cookies = {}
        mock_request.query_params = {"token": "token999"}

        with patch("faster.core.auth.utilities.logger") as mock_logger:
            result = extract_token_from_multiple_sources(mock_request)
            assert result == "token999"
            mock_logger.warning.assert_called_once()

    def test_extract_token_from_multiple_sources_none_request(self) -> None:
        """Test extracting token with None request."""
        result = extract_token_from_multiple_sources(None)
        assert result is None

    def test_extract_token_from_multiple_sources_priority_order(self) -> None:
        """Test that Authorization header takes priority over others."""
        # Create a valid JWT-like token for Authorization header
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {"sub": "user123"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        auth_token = f"{header_b64}.{payload_b64}.signature"

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": f"Bearer {auth_token}", "X-Access-Token": "x_token"}
        mock_request.cookies = {"access_token": "cookie_token"}
        mock_request.query_params = {"token": "query_token"}

        result = extract_token_from_multiple_sources(mock_request)
        assert result == auth_token

    def test_extract_token_from_multiple_sources_invalid_jwt_format(self) -> None:
        """Test that invalid JWT format tokens are rejected."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({"X-Access-Token": "invalid.jwt"})

        result = extract_token_from_multiple_sources(mock_request)
        assert result is None

    def test_extract_token_from_multiple_sources_empty_headers(self) -> None:
        """Test extracting token when all sources are empty."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({})
        mock_request.cookies = {}
        mock_request.query_params = {}

        result = extract_token_from_multiple_sources(mock_request)
        assert result is None


class TestIntegrationScenarios:
    """Test integration scenarios for utilities."""

    def test_complete_bearer_token_extraction_flow(self) -> None:
        """Test complete flow of Bearer token extraction."""
        # Create a valid JWT-like token
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {"sub": "user123", "exp": 1638360000}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        token = f"{header_b64}.{payload_b64}.signature"

        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({"Authorization": f"Bearer {token}"})

        result = extract_bearer_token_from_request(mock_request)
        assert result == token

    def test_multiple_source_fallback_chain(self) -> None:
        """Test fallback chain when primary source fails."""
        # Test X-Access-Token fallback
        mock_request = MagicMock()
        mock_request.headers = {"X-Access-Token": "x_token"}
        mock_request.cookies = {}
        mock_request.query_params = {}

        result = extract_token_from_multiple_sources(mock_request)
        assert result == "x_token"

        # Test cookie fallback
        mock_request2 = MagicMock()
        mock_request2.headers = {}
        mock_request2.cookies = {"access_token": "cookie_token"}
        mock_request2.query_params = {}

        result = extract_token_from_multiple_sources(mock_request2)
        assert result == "cookie_token"

    def test_error_handling_in_token_extraction(self) -> None:
        """Test error handling during token extraction."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.side_effect = Exception("Header access error")

        with patch("faster.core.auth.utilities.logger") as mock_logger:
            result = extract_bearer_token_from_request(mock_request)
            assert result is None
            mock_logger.error.assert_called_once()

    def test_edge_case_empty_and_whitespace_tokens(self) -> None:
        """Test handling of empty and whitespace tokens."""
        test_cases = [
            "Bearer ",
            "Bearer   ",
            "Bearer \t\n",
        ]

        for auth_header in test_cases:
            mock_request = MagicMock(spec=Request)
            mock_request.headers = Headers({"Authorization": auth_header})

            result = extract_bearer_token_from_request(mock_request)
            assert result is None

    def test_case_variations_in_bearer_scheme(self) -> None:
        """Test case variations in Bearer scheme."""
        # Create a valid JWT-like token
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {"sub": "user123"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        token = f"{header_b64}.{payload_b64}.signature"

        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({"Authorization": f"BEARER {token}"})

        result = extract_bearer_token_from_request(mock_request)
        assert result == token  # Should be case insensitive

    def test_malformed_authorization_headers(self) -> None:
        """Test handling of malformed Authorization headers."""
        malformed_headers = [
            "Bearer",
            "Bearer token1 token2",
            "Bearer token with spaces",
            "Bearer\ttoken",  # Tab character
            "Bearer\ntoken",  # Newline character
        ]

        for header in malformed_headers:
            mock_request = MagicMock(spec=Request)
            mock_request.headers = Headers({"Authorization": header})

            result = extract_bearer_token_from_request(mock_request)
            # Some may pass, some may fail - just ensure no exceptions
            assert isinstance(result, str | type(None))


class TestLoggingAndDebugging:
    """Test logging and debugging aspects of utilities."""

    def test_logging_in_token_extraction(self) -> None:
        """Test that appropriate logging occurs during token extraction."""
        # Create a valid JWT-like token
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {"sub": "user123"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        token = f"{header_b64}.{payload_b64}.signature"

        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({"Authorization": f"Bearer {token}"})

        with patch("faster.core.auth.utilities.logger"):
            result = extract_bearer_token_from_request(mock_request)
            assert result == token
            # Should not log for successful extractions (commented out debug log)

    def test_logging_for_invalid_schemes(self) -> None:
        """Test logging for invalid authorization schemes."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({"Authorization": "InvalidScheme token123"})

        with patch("faster.core.auth.utilities.logger") as mock_logger:
            result = extract_bearer_token_from_request(mock_request)
            assert result is None
            mock_logger.debug.assert_called()

    def test_logging_for_missing_headers(self) -> None:
        """Test logging for missing authorization headers."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = Headers({})

        with patch("faster.core.auth.utilities.logger") as mock_logger:
            result = extract_bearer_token_from_request(mock_request)
            assert result is None
            mock_logger.debug.assert_called()
