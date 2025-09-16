"""Unit tests for new authentication repository methods."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from faster.core.auth.repositories import AuthRepository
from faster.core.auth.schemas import User, UserMetadata, UserProfile, UserRole
from faster.core.database import DatabaseManager
from faster.core.exceptions import DBError


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock database session."""
    session = MagicMock()
    # Mock synchronous methods as regular methods
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()

    # Mock async methods as AsyncMock
    session.exec = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    session.scalars = AsyncMock()
    session.flush = AsyncMock()

    return session


@pytest.fixture
def mock_db_manager(mock_session: MagicMock) -> MagicMock:
    """Create a mock database manager."""
    db_manager = MagicMock(spec=DatabaseManager)
    db_manager.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    db_manager.get_session.return_value.__aexit__ = AsyncMock(return_value=None)
    return db_manager


@pytest.fixture
def auth_repository(mock_db_manager: MagicMock) -> AuthRepository:
    """Create an AuthRepository instance for testing."""
    return AuthRepository(db_manager=mock_db_manager)


class TestAccountManagementMethods:
    """Test account management repository methods."""

    @pytest.mark.asyncio
    async def test_deactivate_account_success(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test successful account deactivation."""
        # Mock user
        mock_user = MagicMock(spec=User)
        mock_user.auth_id = "user-123"

        # Mock query result
        mock_result = MagicMock()
        mock_result.first.return_value = mock_user
        mock_session.exec = AsyncMock(return_value=mock_result)

        # Mock transaction context
        with patch.object(auth_repository, "transaction") as mock_transaction:
            mock_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await auth_repository.deactivate_account("user-123")

            assert result is True
            mock_session.add.assert_called_once_with(mock_user)
            mock_session.flush.assert_called_once()
            assert mock_user.in_used == 0

    @pytest.mark.asyncio
    async def test_deactivate_account_user_not_found(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test account deactivation when user is not found."""
        # Mock query result - no user found
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec = AsyncMock(return_value=mock_result)

        # Mock transaction context
        with patch.object(auth_repository, "transaction") as mock_transaction:
            mock_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await auth_repository.deactivate_account("user-123")

            assert result is False

    @pytest.mark.asyncio
    async def test_deactivate_account_empty_user_id(self, auth_repository: AuthRepository) -> None:
        """Test account deactivation with empty user ID."""
        with pytest.raises(ValueError, match="User ID cannot be empty"):
            _ = await auth_repository.deactivate_account("")

    @pytest.mark.asyncio
    async def test_delete_account_success(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test successful account deletion."""
        # Mock user and related data
        mock_user = MagicMock(spec=User)
        mock_metadata = MagicMock(spec=UserMetadata)
        mock_profile = MagicMock(spec=UserProfile)
        mock_role = MagicMock(spec=UserRole)

        # Mock query results
        mock_user_result = MagicMock()
        mock_user_result.first.return_value = mock_user

        mock_metadata_result = MagicMock()
        mock_metadata_result.__iter__ = lambda self: iter([mock_metadata])

        mock_profile_result = MagicMock()
        mock_profile_result.__iter__ = lambda self: iter([mock_profile])

        mock_role_result = MagicMock()
        mock_role_result.__iter__ = lambda self: iter([mock_role])

        mock_session.exec = AsyncMock(
            side_effect=[mock_user_result, mock_metadata_result, mock_profile_result, mock_role_result]
        )

        # Mock transaction context
        with patch.object(auth_repository, "transaction") as mock_transaction:
            mock_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await auth_repository.delete_account("user-123")

            assert result is True
            assert mock_user.in_used == 0
            assert mock_metadata.in_used == 0
            assert mock_profile.in_used == 0
            assert mock_role.in_used == 0

    @pytest.mark.asyncio
    async def test_delete_account_exception(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test account deletion with database exception."""
        mock_session.exec = AsyncMock(side_effect=Exception("Database error"))

        # Mock transaction context
        with patch.object(auth_repository, "transaction") as mock_transaction:
            mock_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(DBError):
                _ = await auth_repository.delete_account("user-123")


class TestUserAdministrationMethods:
    """Test user administration repository methods."""

    @pytest.mark.asyncio
    async def test_ban_user_success(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test successful user banning."""
        # Mock user
        mock_user = MagicMock(spec=User)
        mock_user.auth_id = "target-user-123"

        # Mock query result
        mock_result = MagicMock()
        mock_result.first.return_value = mock_user
        mock_session.exec = AsyncMock(return_value=mock_result)

        # Mock create_or_update_user_metadata
        with patch.object(
            auth_repository, "create_or_update_user_metadata", new_callable=AsyncMock
        ) as mock_update_metadata:
            mock_update_metadata.return_value = None

            # Mock transaction context
            with patch.object(auth_repository, "transaction") as mock_transaction:
                mock_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await auth_repository.ban_user("target-user-123", "admin-123", "Violation")

                assert result is True
                mock_update_metadata.assert_called_once()

    @pytest.mark.asyncio
    async def test_ban_user_not_found(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test user banning when user is not found."""
        # Mock query result - no user found
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec = AsyncMock(return_value=mock_result)

        # Mock transaction context
        with patch.object(auth_repository, "transaction") as mock_transaction:
            mock_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await auth_repository.ban_user("target-user-123", "admin-123", "Violation")

            assert result is False

    @pytest.mark.asyncio
    async def test_ban_user_empty_ids(self, auth_repository: AuthRepository) -> None:
        """Test user banning with empty IDs."""
        with pytest.raises(ValueError, match="Target user ID cannot be empty"):
            _ = await auth_repository.ban_user("", "admin-123", "Violation")

        with pytest.raises(ValueError, match="Admin user ID cannot be empty"):
            _ = await auth_repository.ban_user("target-user-123", "", "Violation")

    @pytest.mark.asyncio
    async def test_unban_user_success(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test successful user unbanning."""
        # Mock create_or_update_user_metadata
        with patch.object(
            auth_repository, "create_or_update_user_metadata", new_callable=AsyncMock
        ) as mock_update_metadata:
            mock_update_metadata.return_value = None

            # Mock transaction context
            with patch.object(auth_repository, "transaction") as mock_transaction:
                mock_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await auth_repository.unban_user("target-user-123", "admin-123")

                assert result is True
                mock_update_metadata.assert_called_once()


class TestRoleManagementMethods:
    """Test role management repository methods."""

    @pytest.mark.asyncio
    async def test_grant_roles_success(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test successful role granting."""
        roles_to_grant = ["moderator", "editor"]

        # Mock current roles query - user has "user" role
        mock_current_roles_result = MagicMock()
        mock_current_roles_result.all.return_value = ["user"]

        # Mock existing role queries - no existing roles for the new ones
        mock_existing_role_result = MagicMock()
        mock_existing_role_result.first.return_value = None

        mock_session.exec = AsyncMock(
            side_effect=[
                mock_current_roles_result,
                mock_existing_role_result,  # For "moderator"
                mock_existing_role_result,  # For "editor"
            ]
        )

        # Mock transaction context
        with patch.object(auth_repository, "transaction") as mock_transaction:
            mock_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await auth_repository.grant_roles("target-user-123", roles_to_grant, "admin-123")

            assert result is True
            # Should add 2 new role objects
            assert mock_session.add.call_count == 2

    @pytest.mark.asyncio
    async def test_grant_roles_with_existing_disabled_role(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test role granting with existing disabled role."""
        roles_to_grant = ["moderator"]

        # Mock current roles query
        mock_current_roles_result = MagicMock()
        mock_current_roles_result.all.return_value = ["user"]

        # Mock existing disabled role
        mock_existing_role = MagicMock(spec=UserRole)
        mock_existing_role.in_used = 0
        mock_existing_role_result = MagicMock()
        mock_existing_role_result.first.return_value = mock_existing_role

        mock_session.exec = AsyncMock(
            side_effect=[
                mock_current_roles_result,
                mock_existing_role_result,
            ]
        )

        # Mock transaction context
        with patch.object(auth_repository, "transaction") as mock_transaction:
            mock_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await auth_repository.grant_roles("target-user-123", roles_to_grant, "admin-123")

            assert result is True
            # Should reactivate existing role
            assert mock_existing_role.in_used == 1
            mock_session.add.assert_called_with(mock_existing_role)

    @pytest.mark.asyncio
    async def test_grant_roles_empty_parameters(self, auth_repository: AuthRepository) -> None:
        """Test role granting with empty parameters."""
        with pytest.raises(ValueError, match="Target user ID cannot be empty"):
            _ = await auth_repository.grant_roles("", ["role"], "admin-123")

        with pytest.raises(ValueError, match="Roles must be a non-empty list"):
            _ = await auth_repository.grant_roles("user-123", [], "admin-123")

        with pytest.raises(ValueError, match="Admin user ID cannot be empty"):
            _ = await auth_repository.grant_roles("user-123", ["role"], "")

    @pytest.mark.asyncio
    async def test_revoke_roles_success(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test successful role revoking."""
        roles_to_revoke = ["moderator"]

        # Mock existing active role
        mock_role = MagicMock(spec=UserRole)
        mock_role.role = "moderator"
        mock_role.in_used = 1

        mock_role_result = MagicMock()
        mock_role_result.first.return_value = mock_role

        mock_session.exec = AsyncMock(return_value=mock_role_result)

        # Mock transaction context
        with patch.object(auth_repository, "transaction") as mock_transaction:
            mock_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await auth_repository.revoke_roles("target-user-123", roles_to_revoke, "admin-123")

            assert result is True
            assert mock_role.in_used == 0
            mock_session.add.assert_called_with(mock_role)

    @pytest.mark.asyncio
    async def test_revoke_roles_non_existent_role(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test role revoking with non-existent role."""
        roles_to_revoke = ["non_existent"]

        # Mock query result - no role found
        mock_role_result = MagicMock()
        mock_role_result.first.return_value = None

        mock_session.exec = AsyncMock(return_value=mock_role_result)

        # Mock transaction context
        with patch.object(auth_repository, "transaction") as mock_transaction:
            mock_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await auth_repository.revoke_roles("target-user-123", roles_to_revoke, "admin-123")

            assert result is True  # Still returns True even if role doesn't exist
            mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_revoke_roles_invalid_parameters(self, auth_repository: AuthRepository) -> None:
        """Test role revoking with invalid parameters."""
        with pytest.raises(ValueError, match="Target user ID cannot be empty"):
            _ = await auth_repository.revoke_roles("", ["role"], "admin-123")

        with pytest.raises(ValueError, match="Roles must be a non-empty list"):
            await auth_repository.revoke_roles("user-123", "not_a_list", "admin-123")  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="Admin user ID cannot be empty"):
            _ = await auth_repository.revoke_roles("user-123", ["role"], "")


class TestErrorHandling:
    """Test error handling in repository methods."""

    @pytest.mark.asyncio
    async def test_deactivate_account_db_error(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test account deactivation with database error."""
        mock_session.exec = AsyncMock(side_effect=Exception("Database connection failed"))

        # Mock transaction context
        with patch.object(auth_repository, "transaction") as mock_transaction:
            mock_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(DBError, match="Failed to deactivate account"):
                _ = await auth_repository.deactivate_account("user-123")

    @pytest.mark.asyncio
    async def test_ban_user_db_error(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test user banning with database error."""
        mock_session.exec = AsyncMock(side_effect=Exception("Database connection failed"))

        # Mock transaction context
        with patch.object(auth_repository, "transaction") as mock_transaction:
            mock_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(DBError, match="Failed to ban user"):
                _ = await auth_repository.ban_user("target-user-123", "admin-123", "Violation")

    @pytest.mark.asyncio
    async def test_grant_roles_db_error(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test role granting with database error."""
        mock_session.exec = AsyncMock(side_effect=Exception("Database connection failed"))

        # Mock transaction context
        with patch.object(auth_repository, "transaction") as mock_transaction:
            mock_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(DBError, match="Failed to grant roles"):
                _ = await auth_repository.grant_roles("target-user-123", ["role"], "admin-123")

    @pytest.mark.asyncio
    async def test_revoke_roles_db_error(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test role revoking with database error."""
        mock_session.exec = AsyncMock(side_effect=Exception("Database connection failed"))

        # Mock transaction context
        with patch.object(auth_repository, "transaction") as mock_transaction:
            mock_transaction.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_transaction.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(DBError, match="Failed to revoke roles"):
                _ = await auth_repository.revoke_roles("target-user-123", ["role"], "admin-123")
