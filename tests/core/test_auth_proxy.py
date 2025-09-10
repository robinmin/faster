import base64
from datetime import datetime
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from faster.core.auth.auth_proxy import AuthProxy
from faster.core.auth.middlewares import get_current_user
from faster.core.auth.models import UserProfileData


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
        # Create a complete UserProfileData with all required fields
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
            "role": "authenticated"
        }"""
        mock_get_user_profile.return_value = cached_user_json

        result = await auth_proxy.get_user_by_id("user-123")

        assert result is not None
        assert result.id == "user-123"
        assert result.email == "test@example.com"
        mock_get_user_profile.assert_called_once_with("user-123")

    @pytest.mark.asyncio
    async def test_get_user_by_id_user_not_found(self, auth_proxy: AuthProxy) -> None:
        """Test getting user by ID when user is not found."""
        with (
            patch("faster.core.auth.auth_proxy.get_user_profile", return_value=None),
            patch.object(AuthProxy, "service_client", new_callable=PropertyMock) as mock_service_client_prop,
        ):
            mock_service_client = MagicMock()
            mock_response = MagicMock()
            mock_response.user = None
            mock_service_client.auth.admin.get_user_by_id.return_value = mock_response
            mock_service_client_prop.return_value = mock_service_client

            result = await auth_proxy.get_user_by_id("nonexistent-user")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_token_missing_user_id(self, auth_proxy: AuthProxy) -> None:
        """Test token authentication with missing user ID in payload."""
        token = "invalid-token"
        with patch.object(auth_proxy, "get_user_id_from_token", new_callable=AsyncMock) as mock_get_user_id:
            mock_get_user_id.return_value = None
            result = await auth_proxy.get_user_by_token(token)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_id_with_cache_hit(self, auth_proxy: AuthProxy) -> None:
        """Test getting user by ID when cache hit occurs."""
        user_id = "user-123"
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
            "role": "authenticated"
        }"""

        with patch("faster.core.auth.auth_proxy.get_user_profile", new_callable=AsyncMock) as mock_get_profile:
            mock_get_profile.return_value = cached_user_json

            result = await auth_proxy.get_user_by_id(user_id)
            assert result is not None
            assert result.id == user_id
            assert result.email == "test@example.com"
            mock_get_profile.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_get_user_by_id_with_cache_miss(self, auth_proxy: AuthProxy) -> None:
        """Test getting user by ID when cache miss occurs."""
        user_id = "user-123"
        mock_user = UserProfileData(
            id=user_id,
            email="test@example.com",
            aud="test",
            role="authenticated",
            app_metadata={},
            user_metadata={},
            created_at=datetime.fromisoformat("2023-01-01T00:00:00"),
        )

        with (
            patch("faster.core.auth.auth_proxy.get_user_profile", return_value=None) as mock_get_profile,
            patch.object(AuthProxy, "service_client", new_callable=PropertyMock) as mock_service_client_prop,
        ):
            mock_service_client = MagicMock()
            mock_response = MagicMock()
            mock_response.user = mock_user
            mock_service_client.auth.admin.get_user_by_id.return_value = mock_response
            mock_service_client_prop.return_value = mock_service_client

            with patch("faster.core.auth.auth_proxy.set_user_profile", new_callable=AsyncMock) as mock_set_profile:
                result = await auth_proxy.get_user_by_id(user_id)
                assert result is not None
                assert result.id == user_id
                mock_get_profile.assert_called_once_with(user_id)
                mock_service_client.auth.admin.get_user_by_id.assert_called_once_with(user_id)
                mock_set_profile.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_by_id_service_error(self, auth_proxy: AuthProxy) -> None:
        """Test getting user by ID when service returns error."""
        user_id = "error-user"

        with (
            patch("faster.core.auth.auth_proxy.get_user_profile", return_value=None),
            patch.object(AuthProxy, "service_client", new_callable=PropertyMock) as mock_service_client_prop,
        ):
            mock_service_client = MagicMock()
            mock_service_client.auth.admin.get_user_by_id.side_effect = Exception("Service error")
            mock_service_client_prop.return_value = mock_service_client

            result = await auth_proxy.get_user_by_id(user_id)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_id_without_cache(self, auth_proxy: AuthProxy) -> None:
        """Test getting user by ID without using cache."""
        user_id = "user-123"
        mock_user = UserProfileData(
            id=user_id,
            email="test@example.com",
            aud="test",
            role="authenticated",
            app_metadata={},
            user_metadata={},
            created_at=datetime.fromisoformat("2023-01-01T00:00:00"),
        )

        with (
            patch.object(AuthProxy, "service_client", new_callable=PropertyMock) as mock_service_client_prop,
            patch("faster.core.auth.auth_proxy.set_user_profile", new_callable=AsyncMock) as mock_set_profile,
        ):
            mock_service_client = MagicMock()
            mock_response = MagicMock()
            mock_response.user = mock_user
            mock_service_client.auth.admin.get_user_by_id.return_value = mock_response
            mock_service_client_prop.return_value = mock_service_client

            result = await auth_proxy.get_user_by_id(user_id, from_cache=False)
            assert result is not None
            assert result.id == user_id
            mock_service_client.auth.admin.get_user_by_id.assert_called_once_with(user_id)
            mock_set_profile.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_id_from_token_success(self, auth_proxy: AuthProxy) -> None:
        """Test JWT token verification success."""
        token = "valid.jwt.token"
        expected_payload = {"sub": "user-123", "aud": "test-audience"}

        with patch.object(auth_proxy, "_extract_token_header_info") as mock_header:
            mock_header.return_value = ("test-key", "RS256")

            with patch.object(auth_proxy, "_get_cached_jwks_key", new_callable=AsyncMock) as mock_get_key:
                mock_key = {"kty": "RSA", "n": "test", "e": "AQAB", "alg": "RS256"}
                mock_get_key.return_value = mock_key

                with patch.object(auth_proxy, "_construct_public_key") as mock_construct_key:
                    mock_public_key = "public_key"
                    mock_construct_key.return_value = mock_public_key

                    with patch.object(auth_proxy, "_verify_jwt_token") as mock_decode:
                        mock_decode.return_value = expected_payload

                        result = await auth_proxy.get_user_id_from_token(token)
                        assert result == expected_payload["sub"]
                        mock_header.assert_called_once_with(token)
                        mock_get_key.assert_called_once_with(
                            key_id="test-key",
                            jwks_url=auth_proxy._supabase_jwks_url,  # type: ignore[reportPrivateUsage, unused-ignore]
                            cache_ttl=auth_proxy._cache_ttl,  # type: ignore[reportPrivateUsage, unused-ignore]
                            auto_refresh=auth_proxy._auto_refresh_jwks,  # type: ignore[reportPrivateUsage, unused-ignore]
                        )
                        mock_decode.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_id_from_token_expired(self, auth_proxy: AuthProxy) -> None:
        """Test JWT token verification with expired token."""
        token = "expired.jwt.token"
        with patch.object(auth_proxy, "_verify_jwt_token", return_value=None):
            result = await auth_proxy.get_user_id_from_token(token)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_id_from_token_invalid_audience(self, auth_proxy: AuthProxy) -> None:
        """Test JWT token verification with invalid audience."""
        token = "invalid.jwt.token"
        with patch.object(auth_proxy, "_verify_jwt_token", return_value=None):
            result = await auth_proxy.get_user_id_from_token(token)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_id_from_token_invalid_token(self, auth_proxy: AuthProxy) -> None:
        """Test JWT token verification with invalid token."""
        token = "invalid.jwt.token"
        with patch.object(auth_proxy, "_verify_jwt_token", return_value=None):
            result = await auth_proxy.get_user_id_from_token(token)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_id_from_token_missing_key_id(self, auth_proxy: AuthProxy) -> None:
        """Test JWT token verification with missing key ID."""
        token = "invalid.jwt.token"
        with patch.object(auth_proxy, "_extract_token_header_info", return_value=(None, None)):
            result = await auth_proxy.get_user_id_from_token(token)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_id_from_token_jwks_fetch_failure(self, auth_proxy: AuthProxy) -> None:
        """Test JWT token verification when JWKS fetch fails."""
        token = "valid.jwt.token"

        with (
            patch.object(auth_proxy, "_extract_token_header_info", return_value=("test-key", "RS256")),
            patch.object(auth_proxy, "_get_cached_jwks_key", new_callable=AsyncMock) as mock_get_key,
        ):
            mock_get_key.return_value = {}

            result = await auth_proxy.get_user_id_from_token(token)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_id_from_token_algorithm_mismatch(self, auth_proxy: AuthProxy) -> None:
        """Test JWT token verification with algorithm mismatch."""
        token = "valid.jwt.token"

        with (
            patch.object(auth_proxy, "_extract_token_header_info", return_value=("test-key", "RS256")),
            patch.object(auth_proxy, "_get_cached_jwks_key", new_callable=AsyncMock) as mock_get_key,
            patch.object(auth_proxy, "_determine_algorithm", return_value=None),
        ):
            mock_get_key.return_value = {"kty": "RSA"}

            result = await auth_proxy.get_user_id_from_token(token)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_id_from_token_public_key_construction_failure(self, auth_proxy: AuthProxy) -> None:
        """Test JWT token verification when public key construction fails."""
        token = "valid.jwt.token"

        with (
            patch.object(auth_proxy, "_extract_token_header_info", return_value=("test-key", "RS256")),
            patch.object(auth_proxy, "_get_cached_jwks_key", new_callable=AsyncMock) as mock_get_key,
            patch.object(auth_proxy, "_determine_algorithm", return_value="RS256"),
            patch.object(auth_proxy, "_construct_public_key", return_value=None),
        ):
            mock_get_key.return_value = {"kty": "RSA"}

            result = await auth_proxy.get_user_id_from_token(token)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_id_from_token_verification_failure(self, auth_proxy: AuthProxy) -> None:
        """Test JWT token verification when token verification fails."""
        token = "invalid.jwt.token"

        with (
            patch.object(auth_proxy, "_extract_token_header_info", return_value=("test-key", "RS256")),
            patch.object(auth_proxy, "_get_cached_jwks_key", new_callable=AsyncMock) as mock_get_key,
            patch.object(auth_proxy, "_determine_algorithm", return_value="RS256"),
            patch.object(auth_proxy, "_construct_public_key", return_value="public_key"),
            patch.object(auth_proxy, "_verify_jwt_token", return_value=None),
        ):
            mock_get_key.return_value = {"kty": "RSA"}

            result = await auth_proxy.get_user_id_from_token(token)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_id_from_token_missing_sub_claim(self, auth_proxy: AuthProxy) -> None:
        """Test JWT token verification when payload missing 'sub' claim."""
        token = "valid.jwt.token"
        payload_without_sub = {"aud": "test-audience", "exp": 1638360000}

        with (
            patch.object(auth_proxy, "_extract_token_header_info", return_value=("test-key", "RS256")),
            patch.object(auth_proxy, "_get_cached_jwks_key", new_callable=AsyncMock) as mock_get_key,
            patch.object(auth_proxy, "_determine_algorithm", return_value="RS256"),
            patch.object(auth_proxy, "_construct_public_key", return_value="public_key"),
            patch.object(auth_proxy, "_verify_jwt_token", return_value=payload_without_sub),
        ):
            mock_get_key.return_value = {"kty": "RSA"}

            result = await auth_proxy.get_user_id_from_token(token)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_token_no_user_in_payload(self, auth_proxy: AuthProxy) -> None:
        """Test token authentication with missing user ID in payload."""
        token = "invalid-token"
        with patch.object(auth_proxy, "get_user_id_from_token", new_callable=AsyncMock) as mock_get_user_id:
            mock_get_user_id.return_value = None
            result = await auth_proxy.get_user_by_token(token)
            assert result is None


class TestAuthProxyJwksCaching:
    """Test AuthProxy JWKS caching functionality."""

    @pytest.mark.asyncio
    async def test_check_redis_cache_hit(self, auth_proxy: AuthProxy) -> None:
        """Test Redis cache hit for JWKS key."""
        key_id = "test-key"
        cached_key = {"kty": "RSA", "kid": key_id}

        with patch("faster.core.auth.auth_proxy.get_jwks_key", new_callable=AsyncMock) as mock_get_jwks:
            mock_get_jwks.return_value = cached_key

            result = await auth_proxy._check_redis_cache(key_id)  # type: ignore[reportPrivateUsage, unused-ignore]
            assert result == cached_key
            mock_get_jwks.assert_called_once_with(key_id)

    @pytest.mark.asyncio
    async def test_check_redis_cache_miss(self, auth_proxy: AuthProxy) -> None:
        """Test Redis cache miss for JWKS key."""
        key_id = "test-key"

        with patch("faster.core.auth.auth_proxy.get_jwks_key", new_callable=AsyncMock) as mock_get_jwks:
            mock_get_jwks.return_value = None

            result = await auth_proxy._check_redis_cache(key_id)  # type: ignore[reportPrivateUsage, unused-ignore]
            assert result is None
            mock_get_jwks.assert_called_once_with(key_id)

    @pytest.mark.asyncio
    async def test_check_redis_cache_exception(self, auth_proxy: AuthProxy) -> None:
        """Test Redis cache exception handling."""
        key_id = "test-key"

        with patch("faster.core.auth.auth_proxy.get_jwks_key", new_callable=AsyncMock) as mock_get_jwks:
            mock_get_jwks.side_effect = Exception("Redis error")

            result = await auth_proxy._check_redis_cache(key_id)  # type: ignore[reportPrivateUsage, unused-ignore]
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_jwks_keys_success(self, auth_proxy: AuthProxy) -> None:
        """Test successful caching of JWKS keys."""
        jwks_data = {
            "keys": [
                {"kid": "key1", "kty": "RSA"},
                {"kid": "key2", "kty": "RSA"},
            ]
        }
        cache_ttl = 3600

        with patch("faster.core.auth.auth_proxy.set_jwks_key", new_callable=AsyncMock) as mock_set_jwks:
            mock_set_jwks.return_value = True

            target_key, cache_failed = await auth_proxy._cache_jwks_keys(jwks_data, cache_ttl)  # type: ignore[reportPrivateUsage, unused-ignore]

            assert target_key == {"kid": "key1", "kty": "RSA"}
            assert cache_failed is False
            assert mock_set_jwks.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_jwks_keys_partial_failure(self, auth_proxy: AuthProxy) -> None:
        """Test partial failure in caching JWKS keys."""
        jwks_data = {
            "keys": [
                {"kid": "key1", "kty": "RSA"},
                {"kid": "key2", "kty": "RSA"},
            ]
        }
        cache_ttl = 3600

        with patch("faster.core.auth.auth_proxy.set_jwks_key", new_callable=AsyncMock) as mock_set_jwks:
            # First call succeeds, second fails
            mock_set_jwks.side_effect = [True, False]

            target_key, cache_failed = await auth_proxy._cache_jwks_keys(jwks_data, cache_ttl)  # type: ignore[reportPrivateUsage, unused-ignore]

            assert target_key == {"kid": "key1", "kty": "RSA"}
            assert cache_failed is True
            assert mock_set_jwks.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_jwks_keys_no_keys(self, auth_proxy: AuthProxy) -> None:
        """Test caching JWKS with no keys."""
        jwks_data: dict[str, Any] = {"keys": []}
        cache_ttl = 3600

        with patch("faster.core.auth.auth_proxy.set_jwks_key", new_callable=AsyncMock) as mock_set_jwks:
            target_key, cache_failed = await auth_proxy._cache_jwks_keys(jwks_data, cache_ttl)  # type: ignore[reportPrivateUsage, unused-ignore]

            assert target_key == {}
            assert cache_failed is False
            mock_set_jwks.assert_not_called()

    @pytest.mark.asyncio
    async def test_find_target_key_found(self, auth_proxy: AuthProxy) -> None:
        """Test finding target key when it exists."""
        jwks_data = {
            "keys": [
                {"kid": "key1", "kty": "RSA"},
                {"kid": "key2", "kty": "RSA"},
            ]
        }
        key_id = "key2"

        result = await auth_proxy._find_target_key(jwks_data, key_id)  # type: ignore[reportPrivateUsage, unused-ignore]
        assert result == {"kid": "key2", "kty": "RSA"}

    @pytest.mark.asyncio
    async def test_find_target_key_not_found(self, auth_proxy: AuthProxy) -> None:
        """Test finding target key when it doesn't exist."""
        jwks_data = {
            "keys": [
                {"kid": "key1", "kty": "RSA"},
                {"kid": "key2", "kty": "RSA"},
            ]
        }
        key_id = "key3"

        result = await auth_proxy._find_target_key(jwks_data, key_id)  # type: ignore[reportPrivateUsage, unused-ignore]
        assert result == {}

    @pytest.mark.asyncio
    async def test_find_target_key_empty_keys(self, auth_proxy: AuthProxy) -> None:
        """Test finding target key with empty keys array."""
        jwks_data: dict[str, Any] = {"keys": []}
        key_id = "key1"

        result = await auth_proxy._find_target_key(jwks_data, key_id)  # type: ignore[reportPrivateUsage, unused-ignore]
        assert result == {}


class TestAuthProxyJwksFetching:
    """Test AuthProxy JWKS fetching functionality."""

    @pytest.mark.asyncio
    async def test_fetch_jwks_from_server_success(self, auth_proxy: AuthProxy) -> None:
        """Test successful JWKS fetch from server."""
        jwks_url = "https://example.com/.well-known/jwks.json"
        expected_data = {"keys": [{"kid": "test-key", "kty": "RSA"}]}

        with patch("faster.core.auth.auth_proxy.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = expected_data
            mock_response.raise_for_status.return_value = None

            # Set up the async context manager
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            # Make get() return the response
            mock_client.get = AsyncMock(return_value=mock_response)

            mock_client_class.return_value = mock_client

            result = await auth_proxy._fetch_jwks_from_server(jwks_url)  # type: ignore[reportPrivateUsage, unused-ignore]
            assert result == expected_data

    @pytest.mark.asyncio
    async def test_fetch_jwks_from_server_timeout(self, auth_proxy: AuthProxy) -> None:
        """Test JWKS fetch timeout."""
        jwks_url = "https://example.com/.well-known/jwks.json"

        with patch("faster.core.auth.auth_proxy.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Timeout")

            # Set up the async context manager
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            mock_client_class.return_value = mock_client

            result = await auth_proxy._fetch_jwks_from_server(jwks_url)  # type: ignore[reportPrivateUsage, unused-ignore]
            assert result == {}

    @pytest.mark.asyncio
    async def test_fetch_jwks_from_server_http_error(self, auth_proxy: AuthProxy) -> None:
        """Test JWKS fetch HTTP error."""
        jwks_url = "https://example.com/.well-known/jwks.json"

        with patch("faster.core.auth.auth_proxy.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = Exception("HTTP 404")

            # Set up the async context manager properly
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            # Make get() return the response
            mock_client.get = AsyncMock(return_value=mock_response)

            mock_client_class.return_value = mock_client

            result = await auth_proxy._fetch_jwks_from_server(jwks_url)  # type: ignore[reportPrivateUsage, unused-ignore]
            assert result == {}

    @pytest.mark.asyncio
    async def test_get_cached_jwks_key_cache_hit(self, auth_proxy: AuthProxy) -> None:
        """Test getting cached JWKS key with cache hit."""
        key_id = "test-key"
        jwks_url = "https://example.com/.well-known/jwks.json"
        cache_ttl = 3600
        auto_refresh = True
        cached_key = {"kty": "RSA", "kid": key_id}

        # Set last refresh to recent time
        auth_proxy.last_refresh = 1000000  # Recent timestamp

        with (
            patch.object(auth_proxy, "_check_redis_cache", new_callable=AsyncMock) as mock_check_cache,
            patch("faster.core.auth.auth_proxy.time.time", return_value=1000050),  # Within TTL
        ):
            mock_check_cache.return_value = cached_key

            result = await auth_proxy._get_cached_jwks_key(key_id, jwks_url, cache_ttl, auto_refresh)  # type: ignore[reportPrivateUsage, unused-ignore]
            assert result == cached_key
            mock_check_cache.assert_called_once_with(key_id)

    @pytest.mark.asyncio
    async def test_get_cached_jwks_key_cache_miss_fetch_success(self, auth_proxy: AuthProxy) -> None:
        """Test getting cached JWKS key with cache miss and successful fetch."""
        key_id = "test-key"
        jwks_url = "https://example.com/.well-known/jwks.json"
        cache_ttl = 3600
        auto_refresh = True
        jwks_data = {"keys": [{"kid": key_id, "kty": "RSA"}]}
        target_key = {"kid": key_id, "kty": "RSA"}

        with (
            patch.object(auth_proxy, "_check_redis_cache", new_callable=AsyncMock) as mock_check_cache,
            patch.object(auth_proxy, "_fetch_jwks_from_server", new_callable=AsyncMock) as mock_fetch,
            patch.object(auth_proxy, "_find_target_key", new_callable=AsyncMock) as mock_find_key,
            patch.object(auth_proxy, "_cache_jwks_keys", new_callable=AsyncMock) as mock_cache_keys,
            patch("faster.core.auth.auth_proxy.time.time", return_value=1000100),
        ):
            mock_check_cache.return_value = None
            mock_fetch.return_value = jwks_data
            mock_find_key.return_value = target_key
            mock_cache_keys.return_value = (target_key, False)

            result = await auth_proxy._get_cached_jwks_key(key_id, jwks_url, cache_ttl, auto_refresh)  # type: ignore[reportPrivateUsage, unused-ignore]

            assert result == target_key
            assert auth_proxy.last_refresh == 1000100

    @pytest.mark.asyncio
    async def test_get_cached_jwks_key_fetch_failure(self, auth_proxy: AuthProxy) -> None:
        """Test getting cached JWKS key when fetch fails."""
        key_id = "test-key"
        jwks_url = "https://example.com/.well-known/jwks.json"
        cache_ttl = 3600
        auto_refresh = True

        with (
            patch.object(auth_proxy, "_check_redis_cache", new_callable=AsyncMock) as mock_check_cache,
            patch.object(auth_proxy, "_fetch_jwks_from_server", new_callable=AsyncMock) as mock_fetch,
        ):
            mock_check_cache.return_value = None
            mock_fetch.return_value = {}

            result = await auth_proxy._get_cached_jwks_key(key_id, jwks_url, cache_ttl, auto_refresh)  # type: ignore[reportPrivateUsage, unused-ignore]
            assert result == {}

    @pytest.mark.asyncio
    async def test_get_user_by_token_user_fetch_error(self, auth_proxy: AuthProxy) -> None:
        """Test token authentication when user fetch fails."""
        token = "valid-token"
        user_id = "user-123"

        with (
            patch.object(auth_proxy, "get_user_id_from_token", new_callable=AsyncMock) as mock_get_user_id,
            patch.object(auth_proxy, "get_user_by_id", new_callable=AsyncMock) as mock_get_user,
        ):
            mock_get_user_id.return_value = user_id
            mock_get_user.side_effect = Exception("Database error")

            result = await auth_proxy.get_user_by_token(token)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_token_empty_token(self, auth_proxy: AuthProxy) -> None:
        """Test token authentication with empty token."""
        result = await auth_proxy.get_user_by_token("")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_token_none_token(self, auth_proxy: AuthProxy) -> None:
        """Test token authentication with None token."""
        result = await auth_proxy.get_user_by_token(None)  # type: ignore[arg-type]
        assert result is None


class TestAuthProxyDependencies:
    """Test AuthProxy dependency functions."""

    @pytest.mark.asyncio
    async def test_get_current_user_success(self) -> None:
        """Test get_current_user with authenticated user."""
        mock_request = MagicMock()
        mock_user = MagicMock(spec=UserProfileData)

        mock_request.state.authenticated = True
        mock_request.state.user = mock_user

        result = await get_current_user(mock_request)

        assert result == mock_user

    @pytest.mark.asyncio
    async def test_get_current_user_not_authenticated(self) -> None:
        """Test get_current_user with unauthenticated request."""
        mock_request = MagicMock()
        mock_request.state.authenticated = False
        result = await get_current_user(mock_request)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_user_no_auth_state(self) -> None:
        """Test get_current_user with no authentication state."""
        mock_request = MagicMock()
        # Simulate missing authenticated attribute
        delattr(mock_request.state, "authenticated")
        result = await get_current_user(mock_request)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_user_authenticated(self) -> None:
        """Test get_current_user with authenticated user."""
        mock_request = MagicMock()
        mock_user = MagicMock(spec=UserProfileData)

        mock_request.state.user = mock_user
        mock_request.state.authenticated = True

        result = await get_current_user(mock_request)

        assert result == mock_user

    @pytest.mark.asyncio
    async def test_get_current_user_no_user_attribute(self) -> None:
        """Test get_current_user with no user attribute."""
        mock_request = MagicMock()

        # Mock hasattr to return False for user attribute
        with patch("faster.core.auth.middlewares.hasattr") as mock_hasattr:
            mock_hasattr.return_value = False

            result = await get_current_user(mock_request)

            assert result is None
