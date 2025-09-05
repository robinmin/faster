import base64
from datetime import datetime
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest

from faster.core.auth.auth_proxy import AuthProxy, get_current_user, get_optional_user
from faster.core.auth.models import SupabaseUser
from faster.core.exceptions import AuthError


def create_mock_jwt_token(payload: dict[str, Any]) -> str:
    """Create a mock JWT token for testing."""
    # Create a simple JWT-like structure (not cryptographically valid, but properly formatted)
    header = {"alg": "RS256", "typ": "JWT", "kid": "test-key"}
    header_json = json.dumps(header, separators=(",", ":"))
    payload_json = json.dumps(payload, separators=(",", ":"))

    header_b64 = base64.urlsafe_b64encode(header_json.encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")
    signature = "mock_signature"

    return f"{header_b64}.{payload_b64}.{signature}"


@pytest.fixture
def auth_proxy_config() -> dict[str, Any]:
    """Auth proxy configuration."""
    return {
        "supabase_url": "https://test.supabase.co",
        "supabase_anon_key": "test-anon-key",
        "supabase_service_key": "test-service-key",
        "supabase_jwks_url": "https://test.supabase.co/.well-known/jwks.json",
        "supabase_audience": "test-audience",
        "cache_ttl": 3600,
        "auto_refresh_jwks": True,
    }


@pytest.fixture
def auth_proxy(auth_proxy_config: dict[str, Any]) -> AuthProxy:
    """Create AuthProxy instance with test configuration."""
    return AuthProxy(**auth_proxy_config)


class TestAuthProxyInitialization:
    """Test AuthProxy initialization."""

    def test_auth_proxy_initialization(self, auth_proxy_config: dict[str, Any]) -> None:
        """Test AuthProxy initialization with valid config."""
        proxy = AuthProxy(**auth_proxy_config)

        # Test that proxy was created successfully
        assert proxy is not None
        assert hasattr(proxy, "client")
        assert hasattr(proxy, "service_client")


class TestAuthProxyClientProperties:
    """Test AuthProxy client properties."""

    @patch("faster.core.auth.auth_proxy.create_client")
    def test_client_property_lazy_initialization(self, mock_create_client: MagicMock, auth_proxy: AuthProxy) -> None:
        """Test client property lazy initialization."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # First access should create client
        client = auth_proxy.client

        assert client == mock_client
        assert mock_create_client.call_count == 1

        # Second access should return cached client
        client2 = auth_proxy.client
        assert client2 == mock_client
        assert mock_create_client.call_count == 1

    @patch("faster.core.auth.auth_proxy.create_client")
    def test_service_client_property_lazy_initialization(
        self, mock_create_client: MagicMock, auth_proxy: AuthProxy
    ) -> None:
        """Test service client property lazy initialization."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # First access should create client
        client = auth_proxy.service_client

        assert client == mock_client
        assert mock_create_client.call_count == 1

        # Second access should return cached client
        client2 = auth_proxy.service_client
        assert client2 == mock_client
        assert mock_create_client.call_count == 1


class TestAuthProxyUserManagement:
    """Test AuthProxy user management functionality."""

    @pytest.mark.asyncio
    @patch("faster.core.auth.auth_proxy.get_user_profile")
    async def test_get_user_by_id_from_cache(self, mock_get_user_profile: AsyncMock, auth_proxy: AuthProxy) -> None:
        """Test getting user by ID from cache."""
        # Create a complete SupabaseUser with all required fields
        cached_user_json = """{
            "id": "user-123",
            "email": "test@example.com",
            "email_confirmed_at": null,
            "phone": null,
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
            "last_sign_in_at": null,
            "app_metadata": {},
            "user_metadata": {},
            "aud": "test",
            "role": "authenticated",
            "phone_confirmed_at": null,
            "confirmation_sent_at": null,
            "recovery_sent_at": null,
            "email_change_sent_at": null,
            "new_email": null,
            "new_phone": null,
            "reconfirmation_token": null,
            "recovery_token": null,
            "email_change_token": null,
            "otp_token": null,
            "otp_sent_at": null,
            "otp_hash": null,
            "otp_method": null,
            "otp_expires_at": null,
            "invited_at": null,
            "action_link": null,
            "is_sso_user": false,
            "deleted_at": null,
            "is_anonymous": false
        }"""
        mock_get_user_profile.return_value = cached_user_json

        result = await auth_proxy.get_user_by_id("user-123")

        assert result.id == "user-123"
        assert result.email == "test@example.com"
        mock_get_user_profile.assert_called_once_with("user-123")

    @pytest.mark.asyncio
    async def test_get_user_by_id_user_not_found(self, auth_proxy: AuthProxy) -> None:
        """Test getting user by ID when user is not found."""
        # Mock the cache to return None and the service client to return None
        with patch("faster.core.auth.auth_proxy.get_user_profile", return_value=None):  # noqa: SIM117
            # Mock the service client
            with patch.object(type(auth_proxy), "service_client", new_callable=MagicMock) as mock_service_client:
                mock_response = MagicMock()
                mock_response.user = None
                mock_service_client.auth.admin.get_user_by_id.return_value = mock_response

                with pytest.raises(AuthError) as exc_info:
                    _ = await auth_proxy.get_user_by_id("nonexistent-user")

                assert exc_info.value.status_code == 404
                assert "User not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_authenticate_token_missing_user_id(self, auth_proxy: AuthProxy) -> None:
        """Test token authentication with missing user ID in payload."""
        payload = {"aud": "test-audience"}  # No 'sub' field
        token = "invalid-token"

        with patch.object(auth_proxy, "verify_jwt_token", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = payload

            with pytest.raises(AuthError, match="User ID not found in token"):
                _ = await auth_proxy.authenticate_token(token)

    @pytest.mark.asyncio
    async def test_refresh_user_cache(self, auth_proxy: AuthProxy) -> None:
        """Test refreshing user cache."""
        user_id = "user-123"
        mock_user = MagicMock(spec=SupabaseUser)

        with patch.object(auth_proxy, "get_user_by_id", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            result = await auth_proxy.refresh_user_cache(user_id)

            assert result == mock_user
            mock_get_user.assert_called_once_with(user_id, use_cache=False)

    @pytest.mark.asyncio
    async def test_invalidate_user_cache(self, auth_proxy: AuthProxy) -> None:
        """Test invalidating user cache."""
        user_id = "user-123"
        mock_user = MagicMock(spec=SupabaseUser)

        with patch.object(auth_proxy, "get_user_by_id", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            await auth_proxy.invalidate_user_cache(user_id)

            mock_get_user.assert_called_once_with(user_id, use_cache=False)

    @pytest.mark.asyncio
    async def test_get_user_by_id_with_cache_hit(self, auth_proxy: AuthProxy) -> None:
        """Test getting user by ID when cache hit occurs."""
        user_id = "user-123"
        # Create complete cached user JSON with all required fields
        cached_user_json = """{
            "id": "user-123",
            "email": "test@example.com",
            "email_confirmed_at": null,
            "phone": null,
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
            "last_sign_in_at": null,
            "app_metadata": {},
            "user_metadata": {},
            "aud": "test",
            "role": "authenticated",
            "phone_confirmed_at": null,
            "confirmation_sent_at": null,
            "recovery_sent_at": null,
            "email_change_sent_at": null,
            "new_email": null,
            "new_phone": null,
            "reconfirmation_token": null,
            "recovery_token": null,
            "email_change_token": null,
            "otp_token": null,
            "otp_sent_at": null,
            "otp_hash": null,
            "otp_method": null,
            "otp_expires_at": null,
            "invited_at": null,
            "action_link": null,
            "is_sso_user": false,
            "deleted_at": null,
            "is_anonymous": false
        }"""

        with patch("faster.core.auth.auth_proxy.get_user_profile", new_callable=AsyncMock) as mock_get_profile:
            mock_get_profile.return_value = cached_user_json

            result = await auth_proxy.get_user_by_id(user_id)
            assert result.id == user_id
            assert result.email == "test@example.com"
            mock_get_profile.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_get_user_by_id_with_cache_miss(self, auth_proxy: AuthProxy) -> None:
        """Test getting user by ID when cache miss occurs."""
        user_id = "user-123"
        mock_user = SupabaseUser(
            id=user_id,
            email="test@example.com",
            aud="test",
            role="authenticated",
            app_metadata={},
            user_metadata={},
            created_at=datetime.fromisoformat("2023-01-01T00:00:00"),
        )

        with patch("faster.core.auth.auth_proxy.get_user_profile", return_value=None) as mock_get_profile, patch.object(auth_proxy, "_service_client", new_callable=MagicMock) as mock_service_client:
                mock_response = MagicMock()
                mock_response.user = mock_user
                mock_service_client.auth.admin.get_user_by_id.return_value = mock_response

                with patch("faster.core.auth.auth_proxy.set_user_profile", new_callable=AsyncMock) as mock_set_profile:
                    result = await auth_proxy.get_user_by_id(user_id)
                    assert result.id == user_id
                    mock_get_profile.assert_called_once_with(user_id)
                    mock_service_client.auth.admin.get_user_by_id.assert_called_once_with(user_id)
                    mock_set_profile.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_by_id_service_error(self, auth_proxy: AuthProxy) -> None:
        """Test getting user by ID when service returns error."""
        user_id = "error-user"

        with patch("faster.core.auth.auth_proxy.get_user_profile", return_value=None), patch.object(auth_proxy, "_service_client", new_callable=MagicMock) as mock_service_client:
                mock_response = MagicMock()
                mock_response.user = None
                mock_service_client.auth.admin.get_user_by_id.return_value = mock_response

                with pytest.raises(AuthError, match="User not found"):
                    _ = await auth_proxy.get_user_by_id(user_id)

    @pytest.mark.asyncio
    async def test_get_user_by_id_without_cache(self, auth_proxy: AuthProxy) -> None:
        """Test getting user by ID without using cache."""
        user_id = "user-123"
        mock_user = SupabaseUser(
            id=user_id,
            email="test@example.com",
            aud="test",
            role="authenticated",
            app_metadata={},
            user_metadata={},
            created_at=datetime.fromisoformat("2023-01-01T00:00:00"),
        )

        with patch.object(auth_proxy, "_service_client", new_callable=MagicMock) as mock_service_client:
            mock_response = MagicMock()
            mock_response.user = mock_user
            mock_service_client.auth.admin.get_user_by_id.return_value = mock_response

            result = await auth_proxy.get_user_by_id(user_id, from_cache=False)
            assert result.id == user_id
            mock_service_client.auth.admin.get_user_by_id.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_verify_jwt_token_success(self, auth_proxy: AuthProxy) -> None:
        """Test JWT token verification success."""
        token = "valid.jwt.token"
        expected_payload = {"sub": "user-123", "aud": "test-audience"}

        with patch("jwt.get_unverified_header") as mock_header:
            mock_header.return_value = {"kid": "test-key"}

            with patch.object(auth_proxy, "_get_jwks_key", new_callable=AsyncMock) as mock_get_key:
                mock_key = {"kty": "RSA", "n": "test", "e": "AQAB"}
                mock_get_key.return_value = mock_key

                with patch("jwt.decode") as mock_decode:
                    mock_decode.return_value = expected_payload

                    result = await auth_proxy.verify_jwt_token(token)
                    assert result == expected_payload
                    mock_header.assert_called_once_with(token)
                    mock_get_key.assert_called_once_with("test-key")
                    mock_decode.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_jwt_token_expired(self, auth_proxy: AuthProxy) -> None:
        """Test JWT token verification with expired token."""
        token = "expired.jwt.token"

        with patch("jwt.get_unverified_header") as mock_header:
            mock_header.return_value = {"kid": "test-key"}

            with patch.object(auth_proxy, "_get_jwks_key", new_callable=AsyncMock) as mock_get_key:
                mock_key = {"kty": "RSA", "n": "test", "e": "AQAB"}
                mock_get_key.return_value = mock_key

                with patch("jwt.decode") as mock_decode:
                    mock_decode.side_effect = jwt.ExpiredSignatureError("Token expired")

                    with pytest.raises(AuthError, match="Token has expired"):
                        _ = await auth_proxy.verify_jwt_token(token)

    @pytest.mark.asyncio
    async def test_verify_jwt_token_invalid_audience(self, auth_proxy: AuthProxy) -> None:
        """Test JWT token verification with invalid audience."""
        token = "invalid.jwt.token"

        with patch("jwt.get_unverified_header") as mock_header:
            mock_header.return_value = {"kid": "test-key"}

            with patch.object(auth_proxy, "_get_jwks_key", new_callable=AsyncMock) as mock_get_key:
                mock_key = {"kty": "RSA", "n": "test", "e": "AQAB"}
                mock_get_key.return_value = mock_key

                with patch("jwt.decode") as mock_decode:
                    mock_decode.side_effect = jwt.InvalidAudienceError("Invalid audience")

                    with pytest.raises(AuthError, match="Invalid token audience"):
                        _ = await auth_proxy.verify_jwt_token(token)

    @pytest.mark.asyncio
    async def test_verify_jwt_token_invalid_token(self, auth_proxy: AuthProxy) -> None:
        """Test JWT token verification with invalid token."""
        token = "invalid.jwt.token"

        with patch("jwt.get_unverified_header") as mock_header:
            mock_header.return_value = {"kid": "test-key"}

            with patch.object(auth_proxy, "_get_jwks_key", new_callable=AsyncMock) as mock_get_key:
                mock_key = {"kty": "RSA", "n": "test", "e": "AQAB"}
                mock_get_key.return_value = mock_key

                with patch("jwt.decode") as mock_decode:
                    mock_decode.side_effect = jwt.InvalidTokenError("Invalid token")

                    with pytest.raises(AuthError, match="Invalid token"):
                        _ = await auth_proxy.verify_jwt_token(token)

    @pytest.mark.asyncio
    async def test_verify_jwt_token_missing_key_id(self, auth_proxy: AuthProxy) -> None:
        """Test JWT token verification with missing key ID."""
        token = "invalid.jwt.token"

        with patch("jwt.get_unverified_header") as mock_header:
            mock_header.return_value = {}  # No 'kid' field

            with pytest.raises(AuthError, match="Missing key ID in JWT header"):
                _ = await auth_proxy.verify_jwt_token(token)

    @pytest.mark.asyncio
    async def test_authenticate_token_no_user_in_payload(self, auth_proxy: AuthProxy) -> None:
        """Test token authentication with missing user ID in payload."""
        payload = {"aud": "test-audience"}  # No 'sub' field
        token = "invalid-token"

        with patch.object(auth_proxy, "verify_jwt_token", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = payload

            with pytest.raises(AuthError, match="User ID not found in token"):
                _ = await auth_proxy.authenticate_token(token)

    @pytest.mark.asyncio
    async def test_authenticate_and_convert_success(self, auth_proxy: AuthProxy) -> None:
        """Test authenticate_and_convert success."""
        token = "valid-token"
        mock_supabase_user = MagicMock(spec=SupabaseUser)
        mock_profile_data = MagicMock()

        with patch.object(auth_proxy, "authenticate_token", new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = mock_supabase_user

            with patch.object(auth_proxy, "_convert_supabase_user_to_profile") as mock_convert:
                mock_convert.return_value = mock_profile_data

                result = await auth_proxy.authenticate_and_convert(token)

                assert result == mock_profile_data
                mock_auth.assert_called_once_with(token)
                mock_convert.assert_called_once_with(mock_supabase_user)


class TestAuthProxyDependencies:
    """Test AuthProxy dependency functions."""

    @pytest.mark.asyncio
    async def test_get_current_user_success(self) -> None:
        """Test get_current_user with authenticated user."""
        mock_request = MagicMock()
        mock_user = MagicMock(spec=SupabaseUser)

        mock_request.state.authenticated = True
        mock_request.state.user = mock_user

        result = await get_current_user(mock_request)

        assert result == mock_user

    @pytest.mark.asyncio
    async def test_get_current_user_not_authenticated(self) -> None:
        """Test get_current_user with unauthenticated request."""
        mock_request = MagicMock()
        mock_request.state.authenticated = False

        with pytest.raises(AuthError, match="Authentication required"):
            _ = await get_current_user(mock_request)

    @pytest.mark.asyncio
    async def test_get_current_user_no_auth_state(self) -> None:
        """Test get_current_user with no authentication state."""
        mock_request = MagicMock()
        # Simulate missing authenticated attribute
        del mock_request.state.authenticated

        with pytest.raises(AuthError, match="Authentication required"):
            _ = await get_current_user(mock_request)

    @pytest.mark.asyncio
    async def test_get_optional_user_authenticated(self) -> None:
        """Test get_optional_user with authenticated user."""
        mock_request = MagicMock()
        mock_user = MagicMock(spec=SupabaseUser)

        mock_request.state.user = mock_user
        mock_request.state.authenticated = True

        result = await get_optional_user(mock_request)

        assert result == mock_user

    @pytest.mark.asyncio
    async def test_get_optional_user_not_authenticated(self) -> None:
        """Test get_optional_user with unauthenticated request."""
        mock_request = MagicMock()
        mock_request.state.authenticated = False
        # No user in state

        result = await get_optional_user(mock_request)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_optional_user_no_user_attribute(self) -> None:
        """Test get_optional_user with no user attribute."""
        mock_request = MagicMock()
        # Simulate missing user attribute
        del mock_request.state.user

        result = await get_optional_user(mock_request)

        assert result is None
