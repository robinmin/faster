"""Unit tests for new authentication service methods."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from faster.core.auth.models import UserProfileData
from faster.core.auth.services import AuthService
from faster.core.config import Settings

# Test constants
TEST_USER_ID = "test-user-123"
TEST_TARGET_USER_ID = "target-user-456"
TEST_EMAIL = "test@example.com"
TEST_ADMIN_USER_ID = "admin-user-789"


@pytest.fixture
def mock_settings() -> Settings:
    """Mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.auth_enabled = True
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_anon_key = "test-anon-key"
    settings.supabase_service_key = "test-service-key"
    settings.supabase_jwks_url = "https://test.supabase.co/.well-known/jwks.json"
    settings.supabase_audience = "test-audience"
    settings.auto_refresh_jwks = True
    settings.jwks_cache_ttl_seconds = 3600
    settings.user_cache_ttl_seconds = 3600
    settings.is_debug = False
    return settings


@pytest.fixture
def mock_user_profile() -> UserProfileData:
    """Mock user profile data."""
    return UserProfileData(
        id=TEST_USER_ID,
        aud="test-audience",
        role="authenticated",
        email=TEST_EMAIL,
        email_confirmed_at=datetime(2023, 1, 1, 0, 0, 0),
        phone=None,
        confirmed_at=datetime(2023, 1, 1, 0, 0, 0),
        last_sign_in_at=datetime(2023, 1, 1, 0, 0, 0),
        is_anonymous=False,
        created_at=datetime(2023, 1, 1, 0, 0, 0),
        updated_at=datetime(2023, 1, 1, 0, 0, 0),
        app_metadata={},
        user_metadata={},
        identities=[],
    )


@pytest.fixture
def auth_service(mock_settings: Settings) -> AuthService:
    """Create an AuthService instance for testing."""
    with patch("faster.core.auth.services.AuthService.setup"):
        service = AuthService()
        # Mock the repository to avoid database initialization issues
        service._repository = MagicMock()  # type: ignore[reportPrivateUsage, unused-ignore]
        return service


class TestPasswordManagementMethods:
    """Test password management service methods."""

    @pytest.mark.asyncio
    async def test_change_password_success(self, auth_service: AuthService) -> None:
        """Test successful password change."""
        with patch.object(auth_service, "_auth_client") as mock_auth_client:
            mock_auth_client.change_password = AsyncMock(return_value=True)

            with patch.object(auth_service, "log_event_raw", new_callable=AsyncMock) as mock_log_event_raw:
                mock_log_event_raw.return_value = True

                result = await auth_service.change_password(TEST_USER_ID, "old_password", "new_password")

                assert result is True
                mock_auth_client.change_password.assert_called_once_with(TEST_USER_ID, "old_password", "new_password")
                mock_log_event_raw.assert_called_once()

    @pytest.mark.asyncio
    async def test_change_password_failure(self, auth_service: AuthService) -> None:
        """Test failed password change."""
        with patch.object(auth_service, "_auth_client") as mock_auth_client:
            mock_auth_client.change_password = AsyncMock(return_value=False)

            result = await auth_service.change_password(TEST_USER_ID, "wrong_password", "new_password")

            assert result is False

    @pytest.mark.asyncio
    async def test_change_password_no_client(self, auth_service: AuthService) -> None:
        """Test password change with no auth client."""
        auth_service._auth_client = None  # type: ignore[reportPrivateUsage, unused-ignore]

        result = await auth_service.change_password(TEST_USER_ID, "old_password", "new_password")

        assert result is False

    @pytest.mark.asyncio
    async def test_initiate_password_reset_success(self, auth_service: AuthService) -> None:
        """Test successful password reset initiation."""
        with patch.object(auth_service, "_auth_client") as mock_auth_client:
            mock_auth_client.initiate_password_reset = AsyncMock(return_value=True)

            with patch.object(auth_service, "log_event_raw", new_callable=AsyncMock) as mock_log_event_raw:
                mock_log_event_raw.return_value = True

                result = await auth_service.initiate_password_reset(TEST_EMAIL)

                assert result is True
                mock_auth_client.initiate_password_reset.assert_called_once_with(TEST_EMAIL)
                mock_log_event_raw.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirm_password_reset_success(self, auth_service: AuthService) -> None:
        """Test successful password reset confirmation."""
        with patch.object(auth_service, "_auth_client") as mock_auth_client:
            mock_auth_client.confirm_password_reset = AsyncMock(return_value=True)

            with patch.object(auth_service, "log_event_raw", new_callable=AsyncMock) as mock_log_event_raw:
                mock_log_event_raw.return_value = True

                result = await auth_service.confirm_password_reset("reset_token", "new_password")

                assert result is True
                mock_auth_client.confirm_password_reset.assert_called_once_with("reset_token", "new_password")
                mock_log_event_raw.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirm_password_reset_failure(self, auth_service: AuthService) -> None:
        """Test failed password reset confirmation."""
        with patch.object(auth_service, "_auth_client") as mock_auth_client:
            mock_auth_client.confirm_password_reset = AsyncMock(return_value=False)

            result = await auth_service.confirm_password_reset("invalid_token", "new_password")

            assert result is False


class TestAccountManagementMethods:
    """Test account management service methods."""

    @pytest.mark.asyncio
    async def test_deactivate_success(self, auth_service: AuthService) -> None:
        """Test successful comprehensive account deactivation."""
        with patch.object(auth_service, "_verify_user_password", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = True

            with patch.object(auth_service, "_repository") as mock_repository:
                mock_repository.deactivate = AsyncMock(return_value=True)

                with patch.object(auth_service, "_auth_client") as mock_auth_client:
                    mock_auth_client.delete_user = AsyncMock(return_value=True)

                    with patch.object(auth_service, "refresh_user_cache", new_callable=AsyncMock) as mock_refresh_cache:
                        mock_refresh_cache.return_value = True

                        with patch.object(auth_service, "log_event_raw", new_callable=AsyncMock) as mock_log_event_raw:
                            mock_log_event_raw.return_value = True

                            result = await auth_service.deactivate(TEST_USER_ID, "correct_password")

                            assert result is True
                            mock_verify.assert_called_once_with(TEST_USER_ID, "correct_password")
                            mock_repository.deactivate.assert_called_once_with(TEST_USER_ID)
                            mock_auth_client.delete_user.assert_called_once_with(TEST_USER_ID)
                            mock_refresh_cache.assert_called_once_with(TEST_USER_ID, force_refresh=True)

    @pytest.mark.asyncio
    async def test_deactivate_wrong_password(self, auth_service: AuthService) -> None:
        """Test account deactivation with wrong password."""
        with patch.object(auth_service, "_verify_user_password", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = False

            result = await auth_service.deactivate(TEST_USER_ID, "wrong_password")

            assert result is False


class TestUserAdministrationMethods:
    """Test user administration service methods."""

    @pytest.mark.asyncio
    async def test_ban_user_success(self, auth_service: AuthService) -> None:
        """Test successful user banning."""
        # Mock user info for lookup
        mock_user = MagicMock()
        mock_user.auth_id = TEST_TARGET_USER_ID

        with patch.object(auth_service, "_repository") as mock_repository:
            mock_repository.ban_user = AsyncMock(return_value=True)
            mock_repository.get_user_by_auth_id = AsyncMock(return_value=mock_user)

            with patch.object(auth_service, "log_event_raw", new_callable=AsyncMock) as mock_log_event_raw:
                mock_log_event_raw.return_value = True

                with patch.object(auth_service, "refresh_user_cache", new_callable=AsyncMock) as mock_refresh_cache:
                    mock_refresh_cache.return_value = True

                    # Mock the database transaction
                    with patch("faster.core.auth.services.get_transaction") as mock_get_transaction:
                        mock_session = MagicMock()
                        mock_get_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                        mock_get_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

                        result = await auth_service.ban_user(TEST_ADMIN_USER_ID, TEST_TARGET_USER_ID, "Violation")

                        assert result is True
                        mock_repository.ban_user.assert_called_once_with(
                            TEST_TARGET_USER_ID, TEST_ADMIN_USER_ID, "Violation"
                        )
                        mock_refresh_cache.assert_called_once_with(TEST_TARGET_USER_ID, force_refresh=True)

    @pytest.mark.asyncio
    async def test_unban_user_success(self, auth_service: AuthService) -> None:
        """Test successful user unbanning."""
        # Mock user info for lookup
        mock_user = MagicMock()
        mock_user.auth_id = TEST_TARGET_USER_ID

        with patch.object(auth_service, "_repository") as mock_repository:
            mock_repository.unban_user = AsyncMock(return_value=True)
            mock_repository.get_user_by_auth_id = AsyncMock(return_value=mock_user)

            with patch.object(auth_service, "log_event_raw", new_callable=AsyncMock) as mock_log_event_raw:
                mock_log_event_raw.return_value = True

                with patch.object(auth_service, "refresh_user_cache", new_callable=AsyncMock) as mock_refresh_cache:
                    mock_refresh_cache.return_value = True

                    # Mock the database transaction
                    with patch("faster.core.auth.services.get_transaction") as mock_get_transaction:
                        mock_session = MagicMock()
                        mock_get_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                        mock_get_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

                        result = await auth_service.unban_user(TEST_ADMIN_USER_ID, TEST_TARGET_USER_ID)

                        assert result is True
                        mock_repository.unban_user.assert_called_once_with(TEST_TARGET_USER_ID, TEST_ADMIN_USER_ID)
                        mock_refresh_cache.assert_called_once_with(TEST_TARGET_USER_ID, force_refresh=True)


class TestAuthServiceCacheRefresh:
    """Tests for cache refresh functionality."""

    @pytest.mark.asyncio
    async def test_refresh_user_cache_with_profile_and_roles(self, auth_service: AuthService) -> None:
        """Test refreshing cache with both profile and roles provided."""
        mock_profile = UserProfileData(
            id=TEST_USER_ID,
            aud="authenticated",
            role="authenticated",
            email="test@example.com",
            created_at=datetime(2023, 1, 1, 0, 0, 0),
            updated_at=datetime(2023, 1, 1, 0, 0, 0),
            app_metadata={"provider": "email"},
            user_metadata={"username": "testuser", "full_name": "Test User"},
        )
        mock_roles = ["admin", "user"]

        with (
            patch("faster.core.auth.services.set_user_profile", new_callable=AsyncMock) as mock_set_profile,
            patch("faster.core.auth.services.user2role_set", new_callable=AsyncMock) as mock_set_roles,
        ):
            mock_set_profile.return_value = True
            mock_set_roles.return_value = True

            result = await auth_service.refresh_user_cache(TEST_USER_ID, user_profile=mock_profile, roles=mock_roles)

            assert result is True
            mock_set_profile.assert_called_once()
            mock_set_roles.assert_called_once_with(TEST_USER_ID, mock_roles)

    @pytest.mark.asyncio
    async def test_refresh_user_cache_force_refresh_loads_data(self, auth_service: AuthService) -> None:
        """Test that force_refresh=True loads missing data from database."""
        mock_profile = UserProfileData(
            id=TEST_USER_ID,
            aud="authenticated",
            role="authenticated",
            email="test@example.com",
            created_at=datetime(2023, 1, 1, 0, 0, 0),
            updated_at=datetime(2023, 1, 1, 0, 0, 0),
            app_metadata={"provider": "email"},
            user_metadata={"username": "testuser", "full_name": "Test User"},
        )
        mock_roles = ["admin", "user"]

        with (
            patch.object(auth_service, "get_user_by_id", new_callable=AsyncMock) as mock_get_user,
            patch.object(auth_service, "get_roles", new_callable=AsyncMock) as mock_get_roles,
            patch("faster.core.auth.services.set_user_profile", new_callable=AsyncMock) as mock_set_profile,
            patch("faster.core.auth.services.user2role_set", new_callable=AsyncMock) as mock_set_roles,
        ):
            mock_get_user.return_value = mock_profile
            mock_get_roles.return_value = mock_roles
            mock_set_profile.return_value = True
            mock_set_roles.return_value = True

            result = await auth_service.refresh_user_cache(TEST_USER_ID, force_refresh=True)

            assert result is True
            mock_get_user.assert_called_once_with(TEST_USER_ID, from_cache=False)
            mock_get_roles.assert_called_once_with(TEST_USER_ID, from_cache=False)
            mock_set_profile.assert_called_once()
            mock_set_roles.assert_called_once_with(TEST_USER_ID, mock_roles)

    @pytest.mark.asyncio
    async def test_refresh_user_cache_skip_none_values_without_force(self, auth_service: AuthService) -> None:
        """Test that None values are skipped when force_refresh=False."""
        with (
            patch.object(auth_service, "get_user_by_id", new_callable=AsyncMock) as mock_get_user,
            patch.object(auth_service, "get_roles", new_callable=AsyncMock) as mock_get_roles,
            patch("faster.core.auth.services.set_user_profile", new_callable=AsyncMock) as mock_set_profile,
            patch("faster.core.auth.services.user2role_set", new_callable=AsyncMock) as mock_set_roles,
        ):
            result = await auth_service.refresh_user_cache(TEST_USER_ID, force_refresh=False)

            assert result is True
            mock_get_user.assert_not_called()
            mock_get_roles.assert_not_called()
            mock_set_profile.assert_not_called()
            mock_set_roles.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_user_cache_empty_user_id_fails(self, auth_service: AuthService) -> None:
        """Test that empty user ID returns False."""
        result = await auth_service.refresh_user_cache("")
        assert result is False

        result = await auth_service.refresh_user_cache("   ")
        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_user_cache_handles_cache_failures(self, auth_service: AuthService) -> None:
        """Test that cache failures are handled gracefully."""
        mock_profile = UserProfileData(
            id=TEST_USER_ID,
            aud="authenticated",
            role="authenticated",
            email="test@example.com",
            created_at=datetime(2023, 1, 1, 0, 0, 0),
            updated_at=datetime(2023, 1, 1, 0, 0, 0),
            app_metadata={"provider": "email"},
            user_metadata={"username": "testuser", "full_name": "Test User"},
        )
        mock_roles = ["admin", "user"]

        with (
            patch("faster.core.auth.services.set_user_profile", new_callable=AsyncMock) as mock_set_profile,
            patch("faster.core.auth.services.user2role_set", new_callable=AsyncMock) as mock_set_roles,
        ):
            mock_set_profile.return_value = False  # Simulate cache failure
            mock_set_roles.return_value = False  # Simulate cache failure

            result = await auth_service.refresh_user_cache(TEST_USER_ID, user_profile=mock_profile, roles=mock_roles)

            assert result is False  # Should return False due to cache failures


class TestRoleManagementMethods:
    """Test role management service methods."""

    @pytest.mark.asyncio
    async def test_get_user_roles_by_id_success(self, auth_service: AuthService) -> None:
        """Test successful admin user roles retrieval."""
        expected_roles = ["admin", "user"]

        with patch.object(auth_service, "get_roles", new_callable=AsyncMock) as mock_get_roles:
            mock_get_roles.return_value = expected_roles

            with patch.object(auth_service, "log_event_raw", new_callable=AsyncMock) as mock_log_event_raw:
                mock_log_event_raw.return_value = True

                result = await auth_service.get_user_roles_by_id(TEST_ADMIN_USER_ID, TEST_TARGET_USER_ID)

                assert result == expected_roles


class TestHelperMethods:
    """Test helper service methods."""

    @pytest.mark.asyncio
    async def test_verify_user_password_success(self, auth_service: AuthService) -> None:
        """Test successful password verification."""
        with patch.object(auth_service, "_auth_client") as mock_auth_client:
            mock_auth_client.verify_password = AsyncMock(return_value=True)

            result = await auth_service._verify_user_password(TEST_USER_ID, "correct_password")  # type: ignore[reportPrivateUsage, unused-ignore]

            assert result is True
            mock_auth_client.verify_password.assert_called_once_with(TEST_USER_ID, "correct_password")

    @pytest.mark.asyncio
    async def test_verify_user_password_failure(self, auth_service: AuthService) -> None:
        """Test failed password verification."""
        with patch.object(auth_service, "_auth_client") as mock_auth_client:
            mock_auth_client.verify_password = AsyncMock(return_value=False)

            result = await auth_service._verify_user_password(TEST_USER_ID, "wrong_password")  # type: ignore[reportPrivateUsage, unused-ignore]

            assert result is False


class TestErrorHandling:
    """Test error handling in service methods."""

    @pytest.mark.asyncio
    async def test_change_password_exception(self, auth_service: AuthService) -> None:
        """Test password change with exception."""
        with patch.object(auth_service, "_auth_client") as mock_auth_client:
            mock_auth_client.change_password.side_effect = Exception("Connection error")

            result = await auth_service.change_password(TEST_USER_ID, "old_password", "new_password")

            assert result is False

    @pytest.mark.asyncio
    async def test_deactivate_exception(self, auth_service: AuthService) -> None:
        """Test account deactivation with exception."""
        with patch.object(auth_service, "_verify_user_password", new_callable=AsyncMock) as mock_verify:
            mock_verify.side_effect = Exception("Verification error")

            result = await auth_service.deactivate(TEST_USER_ID, "password")

            assert result is False
