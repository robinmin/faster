"""Unit tests for new authentication proxy methods."""

from unittest.mock import MagicMock, patch

import pytest

from faster.core.auth.auth_proxy import AuthProxy


@pytest.fixture
def auth_proxy() -> AuthProxy:
    """Create an AuthProxy instance for testing."""
    return AuthProxy(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="test-anon-key",
        supabase_service_role_key="test-service-key",
        supabase_jwks_url="https://test.supabase.co/.well-known/jwks.json",
        supabase_audience="test-audience",
        cache_ttl=3600,
        auto_refresh_jwks=True,
    )


class TestPasswordManagementMethods:
    """Test password management proxy methods."""

    @pytest.mark.asyncio
    async def test_change_password_success(self, auth_proxy: AuthProxy) -> None:
        """Test successful password change via Supabase."""
        # Mock service client
        mock_response = MagicMock()
        mock_response.user = MagicMock()  # Non-null user indicates success

        mock_service_client = MagicMock()
        auth_proxy._service_client = mock_service_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_service_client", mock_service_client):
            mock_service_client.auth.admin.update_user_by_id.return_value = mock_response

            result = await auth_proxy.change_password("user-123", "old_password", "new_password")

            assert result is True
            mock_service_client.auth.admin.update_user_by_id.assert_called_once_with(
                "user-123", {"password": "new_password"}
            )

    @pytest.mark.asyncio
    async def test_change_password_failure(self, auth_proxy: AuthProxy) -> None:
        """Test failed password change via Supabase."""
        # Mock service client with no user in response
        mock_response = MagicMock()
        mock_response.user = None

        mock_service_client = MagicMock()
        auth_proxy._service_client = mock_service_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_service_client", mock_service_client):
            mock_service_client.auth.admin.update_user_by_id.return_value = mock_response

            result = await auth_proxy.change_password("user-123", "old_password", "new_password")

            assert result is False

    @pytest.mark.asyncio
    async def test_change_password_exception(self, auth_proxy: AuthProxy) -> None:
        """Test password change with Supabase exception."""
        mock_service_client = MagicMock()
        auth_proxy._service_client = mock_service_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_service_client", mock_service_client):
            mock_service_client.auth.admin.update_user_by_id.side_effect = Exception("Supabase error")

            result = await auth_proxy.change_password("user-123", "old_password", "new_password")

            assert result is False

    @pytest.mark.asyncio
    async def test_initiate_password_reset_success(self, auth_proxy: AuthProxy) -> None:
        """Test successful password reset initiation via Supabase."""
        mock_client = MagicMock()
        auth_proxy._client = mock_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_client", mock_client):
            mock_client.auth.reset_password_email.return_value = MagicMock()

            result = await auth_proxy.initiate_password_reset("test@example.com")

            assert result is True
            mock_client.auth.reset_password_email.assert_called_once_with("test@example.com")

    @pytest.mark.asyncio
    async def test_initiate_password_reset_exception(self, auth_proxy: AuthProxy) -> None:
        """Test password reset initiation with Supabase exception."""
        mock_client = MagicMock()
        auth_proxy._client = mock_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_client", mock_client):
            mock_client.auth.reset_password_email.side_effect = Exception("Email service error")

            result = await auth_proxy.initiate_password_reset("test@example.com")

            assert result is False

    @pytest.mark.asyncio
    async def test_confirm_password_reset_success(self, auth_proxy: AuthProxy) -> None:
        """Test successful password reset confirmation via Supabase."""
        # Mock client with successful response
        mock_response = MagicMock()
        mock_response.user = MagicMock()  # Non-null user indicates success

        mock_client = MagicMock()
        auth_proxy._client = mock_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_client", mock_client):
            mock_client.auth.update_user.return_value = mock_response

            result = await auth_proxy.confirm_password_reset("reset_token", "new_password")

            assert result is True
            mock_client.auth.update_user.assert_called_once_with({"password": "new_password"})

    @pytest.mark.asyncio
    async def test_confirm_password_reset_failure(self, auth_proxy: AuthProxy) -> None:
        """Test failed password reset confirmation via Supabase."""
        # Mock client with no user in response
        mock_response = MagicMock()
        mock_response.user = None

        mock_client = MagicMock()
        auth_proxy._client = mock_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_client", mock_client):
            mock_client.auth.update_user.return_value = mock_response

            result = await auth_proxy.confirm_password_reset("invalid_token", "new_password")

            assert result is False

    @pytest.mark.asyncio
    async def test_confirm_password_reset_exception(self, auth_proxy: AuthProxy) -> None:
        """Test password reset confirmation with Supabase exception."""
        mock_client = MagicMock()
        auth_proxy._client = mock_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_client", mock_client):
            mock_client.auth.update_user.side_effect = Exception("Token validation error")

            result = await auth_proxy.confirm_password_reset("token", "new_password")

            assert result is False


class TestPasswordVerificationMethods:
    """Test password verification proxy methods."""

    @pytest.mark.asyncio
    async def test_verify_password_success(self, auth_proxy: AuthProxy) -> None:
        """Test successful password verification via Supabase."""
        # Mock service client response for user lookup
        mock_user_response = MagicMock()
        mock_user_response.user = MagicMock()
        mock_user_response.user.email = "test@example.com"

        # Mock client response for sign-in attempt
        mock_auth_response = MagicMock()
        mock_auth_response.user = MagicMock()
        mock_auth_response.user.id = "user-123"

        mock_service_client = MagicMock()
        auth_proxy._service_client = mock_service_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_service_client", mock_service_client):
            mock_service_client.auth.admin.get_user_by_id.return_value = mock_user_response

            mock_client = MagicMock()
        auth_proxy._client = mock_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_client", mock_client):
            mock_client.auth.sign_in_with_password.return_value = mock_auth_response

            result = await auth_proxy.verify_password("user-123", "correct_password")

            assert result is True
            mock_service_client.auth.admin.get_user_by_id.assert_called_once_with("user-123")
            mock_client.auth.sign_in_with_password.assert_called_once_with(
                {"email": "test@example.com", "password": "correct_password"}
            )

    @pytest.mark.asyncio
    async def test_verify_password_user_not_found(self, auth_proxy: AuthProxy) -> None:
        """Test password verification when user is not found."""
        # Mock service client response with no user
        mock_user_response = MagicMock()
        mock_user_response.user = None

        mock_service_client = MagicMock()
        auth_proxy._service_client = mock_service_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_service_client", mock_service_client):
            mock_service_client.auth.admin.get_user_by_id.return_value = mock_user_response

            result = await auth_proxy.verify_password("user-123", "password")

            assert result is False

    @pytest.mark.asyncio
    async def test_verify_password_user_no_email(self, auth_proxy: AuthProxy) -> None:
        """Test password verification when user has no email."""
        # Mock service client response with user but no email
        mock_user_response = MagicMock()
        mock_user_response.user = MagicMock()
        mock_user_response.user.email = None

        mock_service_client = MagicMock()
        auth_proxy._service_client = mock_service_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_service_client", mock_service_client):
            mock_service_client.auth.admin.get_user_by_id.return_value = mock_user_response

            result = await auth_proxy.verify_password("user-123", "password")

            assert result is False

    @pytest.mark.asyncio
    async def test_verify_password_wrong_password(self, auth_proxy: AuthProxy) -> None:
        """Test password verification with wrong password."""
        # Mock service client response for user lookup
        mock_user_response = MagicMock()
        mock_user_response.user = MagicMock()
        mock_user_response.user.email = "test@example.com"

        mock_service_client = MagicMock()
        auth_proxy._service_client = mock_service_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_service_client", mock_service_client):
            mock_service_client.auth.admin.get_user_by_id.return_value = mock_user_response

            mock_client = MagicMock()
        auth_proxy._client = mock_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_client", mock_client):
            mock_client.auth.sign_in_with_password.side_effect = Exception("Invalid credentials")

            result = await auth_proxy.verify_password("user-123", "wrong_password")

            assert result is False

    @pytest.mark.asyncio
    async def test_verify_password_user_id_mismatch(self, auth_proxy: AuthProxy) -> None:
        """Test password verification with user ID mismatch."""
        # Mock service client response for user lookup
        mock_user_response = MagicMock()
        mock_user_response.user = MagicMock()
        mock_user_response.user.email = "test@example.com"

        # Mock client response with different user ID
        mock_auth_response = MagicMock()
        mock_auth_response.user = MagicMock()
        mock_auth_response.user.id = "different-user-456"

        mock_service_client = MagicMock()
        auth_proxy._service_client = mock_service_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_service_client", mock_service_client):
            mock_service_client.auth.admin.get_user_by_id.return_value = mock_user_response

            mock_client = MagicMock()
        auth_proxy._client = mock_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_client", mock_client):
            mock_client.auth.sign_in_with_password.return_value = mock_auth_response

            result = await auth_proxy.verify_password("user-123", "password")

            assert result is False

    @pytest.mark.asyncio
    async def test_verify_password_exception(self, auth_proxy: AuthProxy) -> None:
        """Test password verification with exception."""
        mock_service_client = MagicMock()
        auth_proxy._service_client = mock_service_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_service_client", mock_service_client):
            mock_service_client.auth.admin.get_user_by_id.side_effect = Exception("Service error")

            result = await auth_proxy.verify_password("user-123", "password")

            assert result is False


class TestUserManagementMethods:
    """Test user management proxy methods."""

    @pytest.mark.asyncio
    async def test_delete_user_success(self, auth_proxy: AuthProxy) -> None:
        """Test successful user deletion via Supabase."""
        mock_service_client = MagicMock()
        auth_proxy._service_client = mock_service_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_service_client", mock_service_client):
            mock_service_client.auth.admin.delete_user.return_value = MagicMock()

            result = await auth_proxy.delete_user("user-123")

            assert result is True
            mock_service_client.auth.admin.delete_user.assert_called_once_with("user-123")

    @pytest.mark.asyncio
    async def test_delete_user_exception(self, auth_proxy: AuthProxy) -> None:
        """Test user deletion with Supabase exception."""
        mock_service_client = MagicMock()
        auth_proxy._service_client = mock_service_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_service_client", mock_service_client):
            mock_service_client.auth.admin.delete_user.side_effect = Exception("Deletion failed")

            result = await auth_proxy.delete_user("user-123")

            assert result is False


class TestErrorHandling:
    """Test error handling in proxy methods."""

    @pytest.mark.asyncio
    async def test_change_password_network_error(self, auth_proxy: AuthProxy) -> None:
        """Test password change with network error."""
        mock_service_client = MagicMock()
        auth_proxy._service_client = mock_service_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_service_client", mock_service_client):
            mock_service_client.auth.admin.update_user_by_id.side_effect = ConnectionError("Network error")

            result = await auth_proxy.change_password("user-123", "old_password", "new_password")

            assert result is False

    @pytest.mark.asyncio
    async def test_initiate_password_reset_timeout(self, auth_proxy: AuthProxy) -> None:
        """Test password reset initiation with timeout."""
        mock_client = MagicMock()
        auth_proxy._client = mock_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_client", mock_client):
            mock_client.auth.reset_password_email.side_effect = TimeoutError("Request timeout")

            result = await auth_proxy.initiate_password_reset("test@example.com")

            assert result is False

    @pytest.mark.asyncio
    async def test_verify_password_service_unavailable(self, auth_proxy: AuthProxy) -> None:
        """Test password verification with service unavailable."""
        mock_service_client = MagicMock()
        auth_proxy._service_client = mock_service_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_service_client", mock_service_client):
            mock_service_client.auth.admin.get_user_by_id.side_effect = Exception("Service unavailable")

            result = await auth_proxy.verify_password("user-123", "password")

            assert result is False

    @pytest.mark.asyncio
    async def test_delete_user_permission_error(self, auth_proxy: AuthProxy) -> None:
        """Test user deletion with permission error."""
        mock_service_client = MagicMock()
        auth_proxy._service_client = mock_service_client  # type: ignore[reportPrivateUsage, unused-ignore]
        with patch.object(auth_proxy, "_service_client", mock_service_client):
            mock_service_client.auth.admin.delete_user.side_effect = PermissionError("Insufficient permissions")

            result = await auth_proxy.delete_user("user-123")

            assert result is False


class TestClientInitialization:
    """Test client initialization and properties."""

    @pytest.mark.asyncio
    async def test_lazy_client_initialization(self, auth_proxy: AuthProxy) -> None:
        """Test that clients are initialized lazily."""
        # Initially, clients should be None
        assert auth_proxy._client is None  # type: ignore[reportPrivateUsage, unused-ignore]
        assert auth_proxy._service_client is None  # type: ignore[reportPrivateUsage, unused-ignore]

        with patch("faster.core.auth.auth_proxy.create_client") as mock_create_client:
            mock_create_client.return_value = MagicMock()

            # Accessing client property should initialize it
            client = auth_proxy.client
            assert client is not None
            assert auth_proxy._client is not None  # type: ignore[reportPrivateUsage, unused-ignore]

            # Accessing service_client property should initialize it
            service_client = auth_proxy.service_client
            assert service_client is not None
            assert auth_proxy._service_client is not None  # type: ignore[reportPrivateUsage, unused-ignore]

            # Should have called create_client twice (once for each client)
            assert mock_create_client.call_count == 2

    @pytest.mark.asyncio
    async def test_client_reuse(self, auth_proxy: AuthProxy) -> None:
        """Test that clients are reused after initialization."""
        with patch("faster.core.auth.auth_proxy.create_client") as mock_create_client:
            mock_create_client.return_value = MagicMock()

            # Access client multiple times
            client1 = auth_proxy.client
            client2 = auth_proxy.client

            # Should be the same instance
            assert client1 is client2

            # Should only have called create_client once
            assert mock_create_client.call_count == 1
