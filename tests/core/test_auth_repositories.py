from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from sqlalchemy.exc import SQLAlchemyError

from faster.core.auth.models import UserIdentityData, UserProfileData
from faster.core.auth.repositories import AuthRepository
from faster.core.auth.schemas import User


class TestAuthRepository:
    """Test AuthRepository class."""

    @pytest.fixture
    def auth_repository(self) -> AuthRepository:
        """Create AuthRepository instance."""
        return AuthRepository()

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Fixture for a mocked AsyncSession."""
        session = MagicMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        session.add = MagicMock()
        session.add_all = MagicMock()
        return session

    @pytest.fixture
    def mock_user_profile(self) -> UserProfileData:
        """Fixture for a mock internal UserProfileData."""
        return UserProfileData(
            id=str(uuid.uuid4()),
            aud="authenticated",
            role="authenticated",
            email="test@example.com",
            email_confirmed_at=datetime.now(),
            phone="+1234567890",
            confirmed_at=datetime.now(),
            last_sign_in_at=datetime.now(),
            is_anonymous=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            app_metadata={"provider": "email"},
            user_metadata={"name": "Test User"},
            identities=[],
        )

    def test_auth_repository_initialization(self) -> None:
        """Test AuthRepository initialization."""
        repo = AuthRepository()
        assert repo is not None

    @pytest.mark.asyncio
    async def test_check_user_profile_exists_true(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test check_user_profile_exists returns True when profile exists."""
        # This is a mock implementation - in a real test, you would set up the database query mock
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()  # Simulate user found
        mock_session.execute.return_value = mock_result

        result = await auth_repository.check_user_profile_exists(mock_session, "user-123")

        assert result is True
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_user_profile_exists_false(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test check_user_profile_exists returns False when profile doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Simulate user not found
        mock_session.execute.return_value = mock_result

        result = await auth_repository.check_user_profile_exists(mock_session, "user-123")

        assert result is False
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_user_profile_exists_exception(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test check_user_profile_exists returns False when an exception occurs."""
        mock_session.execute.side_effect = Exception("Database error")

        result = await auth_repository.check_user_profile_exists(mock_session, "user-123")

        assert result is False
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_by_auth_id_found(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test get_user_by_auth_id when user is found."""
        mock_user = User(id=uuid.uuid4(), auth_id="auth-123", aud="test-aud", role="user", email="test@example.com")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        user = await auth_repository.get_user_by_auth_id(mock_session, "auth-123")

        assert user is not None
        assert user.auth_id == "auth-123"
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_by_auth_id_not_found(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test get_user_by_auth_id when user is not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        user = await auth_repository.get_user_by_auth_id(mock_session, "auth-123")

        assert user is None
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_by_auth_id_exception(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test get_user_by_auth_id handles database exceptions."""
        mock_session.execute.side_effect = SQLAlchemyError("DB connection failed")

        user = await auth_repository.get_user_by_auth_id(mock_session, "auth-123")

        assert user is None

    @pytest.mark.asyncio
    async def test_create_or_update_user_creates_new(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_profile: UserProfileData
    ) -> None:
        """Test create_or_update_user creates a new user."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        user_data = {
            "id": mock_user_profile.id,
            "aud": mock_user_profile.aud,
            "role": mock_user_profile.role,
            "email": mock_user_profile.email,
            "email_confirmed_at": mock_user_profile.email_confirmed_at,
            "phone": mock_user_profile.phone,
            "confirmed_at": mock_user_profile.confirmed_at,
            "last_sign_in_at": mock_user_profile.last_sign_in_at,
            "is_anonymous": mock_user_profile.is_anonymous,
            "created_at": mock_user_profile.created_at,
            "updated_at": mock_user_profile.updated_at,
        }
        new_user = await auth_repository.create_or_update_user(mock_session, user_data)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        assert new_user.auth_id == mock_user_profile.id
        assert new_user.email == mock_user_profile.email

    @pytest.mark.asyncio
    async def test_create_or_update_user_updates_existing(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_profile: UserProfileData
    ) -> None:
        """Test create_or_update_user updates an existing user."""
        existing_user = User(
            id=uuid.uuid4(), auth_id=mock_user_profile.id, aud="test-aud", role="user", email="old@example.com"
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_session.execute.return_value = mock_result

        user_data = {
            "id": mock_user_profile.id,
            "aud": mock_user_profile.aud,
            "role": mock_user_profile.role,
            "email": mock_user_profile.email,
            "email_confirmed_at": mock_user_profile.email_confirmed_at,
            "phone": mock_user_profile.phone,
            "confirmed_at": mock_user_profile.confirmed_at,
            "last_sign_in_at": mock_user_profile.last_sign_in_at,
            "is_anonymous": mock_user_profile.is_anonymous,
            "created_at": mock_user_profile.created_at,
            "updated_at": mock_user_profile.updated_at,
        }
        updated_user = await auth_repository.create_or_update_user(mock_session, user_data)

        mock_session.add.assert_not_called()
        mock_session.flush.assert_awaited_once()
        assert updated_user.id == existing_user.id
        assert updated_user.email == mock_user_profile.email

    @pytest.mark.asyncio
    async def test_create_or_update_user_metadata(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test create_or_update_user_metadata."""
        user_auth_id = "auth-123"
        metadata = {"key1": "value1", "key2": 123}

        await auth_repository.create_or_update_user_metadata(mock_session, user_auth_id, "app", metadata)

        # Check that delete was called
        mock_session.execute.assert_awaited_once()
        # Check that add_all was called with correct number of items
        mock_session.add_all.assert_called_once()
        assert len(mock_session.add_all.call_args[0][0]) == 2

    @pytest.mark.asyncio
    async def test_create_or_update_user_identities(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test create_or_update_user_identities."""
        user_auth_id = "auth-123"
        identities = [
            UserIdentityData(
                identity_id=str(uuid.uuid4()),
                id="provider-user-1",
                user_id=user_auth_id,
                identity_data={"sub": "123"},
                provider="google",
                last_sign_in_at=datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        ]

        await auth_repository.create_or_update_user_identities(mock_session, user_auth_id, identities)

        mock_session.execute.assert_awaited_once()
        mock_session.add_all.assert_called_once()
        # Called once for identities (consolidated table)
        assert len(mock_session.add_all.call_args_list) == 1

    @pytest.mark.asyncio
    async def test_create_or_update_user_with_data(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_profile: UserProfileData
    ) -> None:
        """Test create_or_update_user with user data."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        user_data = {
            "id": mock_user_profile.id,
            "aud": mock_user_profile.aud,
            "role": mock_user_profile.role,
            "email": mock_user_profile.email,
            "email_confirmed_at": mock_user_profile.email_confirmed_at,
            "phone": mock_user_profile.phone,
            "confirmed_at": mock_user_profile.confirmed_at,
            "last_sign_in_at": mock_user_profile.last_sign_in_at,
            "is_anonymous": mock_user_profile.is_anonymous,
            "created_at": mock_user_profile.created_at,
            "updated_at": mock_user_profile.updated_at,
        }
        user = await auth_repository.create_or_update_user(mock_session, user_data)

        assert user is not None
        assert user.auth_id == mock_user_profile.id
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_or_update_user_exception(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_profile: UserProfileData
    ) -> None:
        """Test create_or_update_user raises exceptions."""
        user_data = {
            "id": mock_user_profile.id,
            "aud": mock_user_profile.aud,
            "role": mock_user_profile.role,
            "email": mock_user_profile.email,
            "email_confirmed_at": mock_user_profile.email_confirmed_at,
            "phone": mock_user_profile.phone,
            "confirmed_at": mock_user_profile.confirmed_at,
            "last_sign_in_at": mock_user_profile.last_sign_in_at,
            "is_anonymous": mock_user_profile.is_anonymous,
            "created_at": mock_user_profile.created_at,
            "updated_at": mock_user_profile.updated_at,
        }
        mock_session.execute.side_effect = SQLAlchemyError("DB Error")

        with pytest.raises(SQLAlchemyError):
            await auth_repository.create_or_update_user(mock_session, user_data)
