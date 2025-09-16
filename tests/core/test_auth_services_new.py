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
        return service


class TestPasswordManagementMethods:
    """Test password management service methods."""

    @pytest.mark.asyncio
    async def test_change_password_success(self, auth_service: AuthService) -> None:
        """Test successful password change."""
        with patch.object(auth_service, "_auth_client") as mock_auth_client:
            mock_auth_client.change_password = AsyncMock(return_value=True)

            with patch.object(auth_service, "log_event", new_callable=AsyncMock) as mock_log_event:
                mock_log_event.return_value = True

                result = await auth_service.change_password(TEST_USER_ID, "old_password", "new_password")

                assert result is True
                mock_auth_client.change_password.assert_called_once_with(TEST_USER_ID, "old_password", "new_password")
                mock_log_event.assert_called_once()

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

            with patch.object(auth_service, "log_event", new_callable=AsyncMock) as mock_log_event:
                mock_log_event.return_value = True

                result = await auth_service.initiate_password_reset(TEST_EMAIL)

                assert result is True
                mock_auth_client.initiate_password_reset.assert_called_once_with(TEST_EMAIL)
                mock_log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirm_password_reset_success(self, auth_service: AuthService) -> None:
        """Test successful password reset confirmation."""
        with patch.object(auth_service, "_auth_client") as mock_auth_client:
            mock_auth_client.confirm_password_reset = AsyncMock(return_value=True)

            with patch.object(auth_service, "log_event", new_callable=AsyncMock) as mock_log_event:
                mock_log_event.return_value = True

                result = await auth_service.confirm_password_reset("reset_token", "new_password")

                assert result is True
                mock_auth_client.confirm_password_reset.assert_called_once_with("reset_token", "new_password")
                mock_log_event.assert_called_once()

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
    async def test_deactivate_account_success(self, auth_service: AuthService) -> None:
        """Test successful account deactivation."""
        with patch.object(auth_service, "_verify_user_password", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = True

            with patch.object(auth_service, "_repository") as mock_repository:
                mock_repository.deactivate_account = AsyncMock(return_value=True)

                with patch.object(auth_service, "log_event", new_callable=AsyncMock) as mock_log_event:
                    mock_log_event.return_value = True

                    result = await auth_service.deactivate_account(TEST_USER_ID, "correct_password")

                    assert result is True
                    mock_verify.assert_called_once_with(TEST_USER_ID, "correct_password")
                    mock_repository.deactivate_account.assert_called_once_with(TEST_USER_ID)

    @pytest.mark.asyncio
    async def test_deactivate_account_wrong_password(self, auth_service: AuthService) -> None:
        """Test account deactivation with wrong password."""
        with patch.object(auth_service, "_verify_user_password", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = False

            result = await auth_service.deactivate_account(TEST_USER_ID, "wrong_password")

            assert result is False

    @pytest.mark.asyncio
    async def test_delete_account_success(self, auth_service: AuthService) -> None:
        """Test successful account deletion."""
        with patch.object(auth_service, "_verify_user_password", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = True

            with patch.object(auth_service, "_repository") as mock_repository:
                mock_repository.delete_account = AsyncMock(return_value=True)

                with patch.object(auth_service, "_auth_client") as mock_auth_client:
                    mock_auth_client.delete_user = AsyncMock(return_value=True)

                    with patch.object(auth_service, "log_event", new_callable=AsyncMock) as mock_log_event:
                        mock_log_event.return_value = True

                        result = await auth_service.delete_account(TEST_USER_ID, "correct_password")

                        assert result is True
                        mock_repository.delete_account.assert_called_once_with(TEST_USER_ID)
                        mock_auth_client.delete_user.assert_called_once_with(TEST_USER_ID)

    @pytest.mark.asyncio
    async def test_delete_account_no_repository(self, auth_service: AuthService) -> None:
        """Test account deletion with no repository."""
        auth_service._repository = None  # type: ignore[reportPrivateUsage, unused-ignore]

        result = await auth_service.delete_account(TEST_USER_ID, "password")

        assert result is False


class TestUserAdministrationMethods:
    """Test user administration service methods."""

    @pytest.mark.asyncio
    async def test_ban_user_success(self, auth_service: AuthService) -> None:
        """Test successful user banning."""
        with patch.object(auth_service, "_check_admin_permission", new_callable=AsyncMock) as mock_check_permission:
            mock_check_permission.return_value = True

            with patch.object(auth_service, "_repository") as mock_repository:
                mock_repository.ban_user = AsyncMock(return_value=True)

                with patch.object(auth_service, "log_event", new_callable=AsyncMock) as mock_log_event:
                    mock_log_event.return_value = True

                    result = await auth_service.ban_user(TEST_ADMIN_USER_ID, TEST_TARGET_USER_ID, "Violation")

                    assert result is True
                    mock_check_permission.assert_called_once_with(TEST_ADMIN_USER_ID, "ban_user")
                    mock_repository.ban_user.assert_called_once_with(
                        TEST_TARGET_USER_ID, TEST_ADMIN_USER_ID, "Violation"
                    )

    @pytest.mark.asyncio
    async def test_ban_user_insufficient_permissions(self, auth_service: AuthService) -> None:
        """Test user banning with insufficient permissions."""
        with patch.object(auth_service, "_check_admin_permission", new_callable=AsyncMock) as mock_check_permission:
            mock_check_permission.return_value = False

            result = await auth_service.ban_user(TEST_USER_ID, TEST_TARGET_USER_ID, "Violation")

            assert result is False

    @pytest.mark.asyncio
    async def test_unban_user_success(self, auth_service: AuthService) -> None:
        """Test successful user unbanning."""
        with patch.object(auth_service, "_check_admin_permission", new_callable=AsyncMock) as mock_check_permission:
            mock_check_permission.return_value = True

            with patch.object(auth_service, "_repository") as mock_repository:
                mock_repository.unban_user = AsyncMock(return_value=True)

                with patch.object(auth_service, "log_event", new_callable=AsyncMock) as mock_log_event:
                    mock_log_event.return_value = True

                    result = await auth_service.unban_user(TEST_ADMIN_USER_ID, TEST_TARGET_USER_ID)

                    assert result is True
                    mock_repository.unban_user.assert_called_once_with(TEST_TARGET_USER_ID, TEST_ADMIN_USER_ID)


class TestRoleManagementMethods:
    """Test role management service methods."""

    @pytest.mark.asyncio
    async def test_grant_roles_success(self, auth_service: AuthService) -> None:
        """Test successful role granting."""
        roles = ["moderator", "editor"]

        with patch.object(auth_service, "_check_admin_permission", new_callable=AsyncMock) as mock_check_permission:
            mock_check_permission.return_value = True

            with patch.object(auth_service, "_repository") as mock_repository:
                mock_repository.grant_roles = AsyncMock(return_value=True)

                with patch.object(auth_service, "get_roles", new_callable=AsyncMock) as mock_get_roles:
                    mock_get_roles.return_value = ["user"]

                    with patch("faster.core.auth.services.user2role_set", new_callable=AsyncMock) as mock_cache_set:
                        mock_cache_set.return_value = True

                        with patch.object(auth_service, "log_event", new_callable=AsyncMock) as mock_log_event:
                            mock_log_event.return_value = True

                            result = await auth_service.grant_roles(TEST_ADMIN_USER_ID, TEST_TARGET_USER_ID, roles)

                            assert result is True
                            mock_repository.grant_roles.assert_called_once_with(
                                TEST_TARGET_USER_ID, roles, TEST_ADMIN_USER_ID
                            )

    @pytest.mark.asyncio
    async def test_revoke_roles_success(self, auth_service: AuthService) -> None:
        """Test successful role revoking."""
        roles = ["moderator"]

        with patch.object(auth_service, "_check_admin_permission", new_callable=AsyncMock) as mock_check_permission:
            mock_check_permission.return_value = True

            with patch.object(auth_service, "_repository") as mock_repository:
                mock_repository.revoke_roles = AsyncMock(return_value=True)

                with patch.object(auth_service, "get_roles", new_callable=AsyncMock) as mock_get_roles:
                    mock_get_roles.return_value = ["user", "moderator"]

                    with patch("faster.core.auth.services.user2role_set", new_callable=AsyncMock) as mock_cache_set:
                        mock_cache_set.return_value = True

                        with patch.object(auth_service, "log_event", new_callable=AsyncMock) as mock_log_event:
                            mock_log_event.return_value = True

                            result = await auth_service.revoke_roles(TEST_ADMIN_USER_ID, TEST_TARGET_USER_ID, roles)

                            assert result is True
                            mock_repository.revoke_roles.assert_called_once_with(
                                TEST_TARGET_USER_ID, roles, TEST_ADMIN_USER_ID
                            )

    @pytest.mark.asyncio
    async def test_get_user_roles_admin_success(self, auth_service: AuthService) -> None:
        """Test successful admin user roles retrieval."""
        expected_roles = ["admin", "user"]

        with patch.object(auth_service, "_check_admin_permission", new_callable=AsyncMock) as mock_check_permission:
            mock_check_permission.return_value = True

            with patch.object(auth_service, "get_roles", new_callable=AsyncMock) as mock_get_roles:
                mock_get_roles.return_value = expected_roles

                with patch.object(auth_service, "log_event", new_callable=AsyncMock) as mock_log_event:
                    mock_log_event.return_value = True

                    result = await auth_service.get_user_roles_admin(TEST_ADMIN_USER_ID, TEST_TARGET_USER_ID)

                    assert result == expected_roles
                    mock_check_permission.assert_called_once_with(TEST_ADMIN_USER_ID, "view_user_roles")

    @pytest.mark.asyncio
    async def test_get_user_roles_admin_permission_denied(self, auth_service: AuthService) -> None:
        """Test admin user roles retrieval with permission denied."""
        with patch.object(auth_service, "_check_admin_permission", new_callable=AsyncMock) as mock_check_permission:
            mock_check_permission.return_value = False

            result = await auth_service.get_user_roles_admin(TEST_USER_ID, TEST_TARGET_USER_ID)

            assert result is None


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

    @pytest.mark.asyncio
    async def test_check_admin_permission_success(self, auth_service: AuthService) -> None:
        """Test successful admin permission check."""
        with patch.object(auth_service, "get_roles", new_callable=AsyncMock) as mock_get_roles:
            mock_get_roles.return_value = ["admin", "user"]

            result = await auth_service._check_admin_permission(TEST_ADMIN_USER_ID, "ban_user")  # type: ignore[reportPrivateUsage, unused-ignore]

            assert result is True

    @pytest.mark.asyncio
    async def test_check_admin_permission_failure(self, auth_service: AuthService) -> None:
        """Test failed admin permission check."""
        with patch.object(auth_service, "get_roles", new_callable=AsyncMock) as mock_get_roles:
            mock_get_roles.return_value = ["user"]  # No admin roles

            result = await auth_service._check_admin_permission(TEST_USER_ID, "ban_user")  # type: ignore[reportPrivateUsage, unused-ignore]

            assert result is False

    @pytest.mark.asyncio
    async def test_check_admin_permission_exception(self, auth_service: AuthService) -> None:
        """Test admin permission check with exception."""
        with patch.object(auth_service, "get_roles", new_callable=AsyncMock) as mock_get_roles:
            mock_get_roles.side_effect = Exception("Database error")

            result = await auth_service._check_admin_permission(TEST_USER_ID, "ban_user")  # type: ignore[reportPrivateUsage, unused-ignore]

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
    async def test_deactivate_account_exception(self, auth_service: AuthService) -> None:
        """Test account deactivation with exception."""
        with patch.object(auth_service, "_verify_user_password", new_callable=AsyncMock) as mock_verify:
            mock_verify.side_effect = Exception("Verification error")

            result = await auth_service.deactivate_account(TEST_USER_ID, "password")

            assert result is False

    @pytest.mark.asyncio
    async def test_ban_user_exception(self, auth_service: AuthService) -> None:
        """Test user banning with exception."""
        with patch.object(auth_service, "_check_admin_permission", new_callable=AsyncMock) as mock_check_permission:
            mock_check_permission.side_effect = Exception("Permission check error")

            result = await auth_service.ban_user(TEST_ADMIN_USER_ID, TEST_TARGET_USER_ID, "Violation")

            assert result is False

    @pytest.mark.asyncio
    async def test_grant_roles_exception(self, auth_service: AuthService) -> None:
        """Test role granting with exception."""
        with patch.object(auth_service, "_check_admin_permission", new_callable=AsyncMock) as mock_check_permission:
            mock_check_permission.side_effect = Exception("Permission error")

            result = await auth_service.grant_roles(TEST_ADMIN_USER_ID, TEST_TARGET_USER_ID, ["moderator"])

            assert result is False
