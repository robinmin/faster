from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from supabase_auth.types import User as UserProfile

from faster.core.auth.auth_proxy import AuthProxy, get_current_user, get_optional_user
from faster.core.exceptions import AuthError


@pytest.fixture
def auth_proxy_config() -> dict[str, str]:
    """Auth proxy configuration."""
    return {
        "supabase_url": "https://test.supabase.co",
        "supabase_anon_key": "test-anon-key",
        "supabase_service_key": "test-service-key",
        "supabase_jwks_url": "https://test.supabase.co/.well-known/jwks.json",
        "supabase_audience": "test-audience",
    }


@pytest.fixture
def auth_proxy(auth_proxy_config: dict[str, str]) -> AuthProxy:
    """Create AuthProxy instance with test configuration."""
    return AuthProxy(**auth_proxy_config)


class TestAuthProxyInitialization:
    """Test AuthProxy initialization."""

    def test_auth_proxy_initialization(self, auth_proxy_config: dict[str, str]) -> None:
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
        cached_user = UserProfile(
            id="user-123",
            email="test@example.com",
            email_confirmed_at=None,
            phone=None,
            created_at="2023-01-01T00:00:00Z",
            updated_at="2023-01-01T00:00:00Z",
            last_sign_in_at=None,
            app_metadata={},
            user_metadata={},
            aud="test",
            role="authenticated",
        )
        mock_get_user_profile.return_value = cached_user

        _ = await auth_proxy.get_user_by_id("user-123")

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
        mock_user = MagicMock(spec=UserProfile)

        with patch.object(auth_proxy, "get_user_by_id", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            result = await auth_proxy.refresh_user_cache(user_id)

            assert result == mock_user
            mock_get_user.assert_called_once_with(user_id, use_cache=False)


class TestAuthProxyDependencies:
    """Test AuthProxy dependency functions."""

    @pytest.mark.asyncio
    async def test_get_current_user_success(self) -> None:
        """Test get_current_user with authenticated user."""
        mock_request = MagicMock()
        mock_user = MagicMock(spec=UserProfile)

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
        mock_user = MagicMock(spec=UserProfile)

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
