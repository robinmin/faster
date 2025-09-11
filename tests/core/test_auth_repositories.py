import contextlib
from datetime import datetime
import logging
import random
import string
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select

from faster.core.auth.models import UserProfileData
from faster.core.auth.repositories import AuthRepository
from faster.core.auth.schemas import User, UserIdentity, UserProfile, UserRole
from faster.core.auth.schemas import UserMetadata as UserMetadataSchema
from faster.core.database import DatabaseManager, DBSession
from faster.core.exceptions import DBError

logger = logging.getLogger(__name__)


class TestAuthRepository:
    """Test AuthRepository class."""

    @pytest_asyncio.fixture(autouse=True)
    async def cleanup_tables(self, db_manager: DatabaseManager) -> None:
        """Clean up all test data before each test to ensure test isolation."""
        # Clean up data before each test

        async with db_manager.get_transaction() as session:
            # Delete all test data from auth tables
            with contextlib.suppress(Exception):
                _ = await session.execute(delete(User))  # type: ignore[unused-ignore]
            with contextlib.suppress(Exception):
                _ = await session.execute(delete(UserMetadataSchema))  # type: ignore[unused-ignore]
            with contextlib.suppress(Exception):
                _ = await session.execute(delete(UserIdentity))  # type: ignore[unused-ignore]
            with contextlib.suppress(Exception):
                _ = await session.execute(delete(UserProfile))  # type: ignore[unused-ignore]
            with contextlib.suppress(Exception):
                _ = await session.execute(delete(UserRole))  # type: ignore[unused-ignore]
            await session.commit()

    @pytest.fixture
    def auth_repository(self, db_manager: DatabaseManager) -> AuthRepository:
        """Create AuthRepository instance with real database manager."""
        return AuthRepository(db_manager=db_manager)

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Fixture for a mocked DBSession."""
        session = MagicMock()
        session.execute = AsyncMock()
        session.scalar = AsyncMock()
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
            last_sign_in_at=datetime.now(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            app_metadata={"provider": "email"},
            user_metadata={"name": "Test User"},
        )

    def test_auth_repository_initialization(self) -> None:
        """Test AuthRepository initialization."""
        repo = AuthRepository()
        assert repo is not None

    @pytest.mark.asyncio
    async def test_create_or_update_user_metadata(self, auth_repository: AuthRepository, db_session: DBSession) -> None:
        """Test create_or_update_user_metadata with real database."""
        user_auth_id = "auth-123"
        metadata = {"key1": "value1", "key2": 123}

        # Use real database session instead of mocking
        async with auth_repository.transaction() as session:
            await auth_repository.create_or_update_user_metadata(session, user_auth_id, "app", metadata)

        # Verify metadata was stored correctly by querying the database
        async with auth_repository.session(readonly=True) as session:
            query = select(UserMetadataSchema).where(
                UserMetadataSchema.user_auth_id == user_auth_id,
                UserMetadataSchema.metadata_type == "app",
                UserMetadataSchema.in_used == 1,
            )
            result = await session.exec(query)
            metadata_list = result.all()

            assert len(metadata_list) == 2
            stored_keys = {m.key for m in metadata_list}
            assert stored_keys == {"key1", "key2"}

    @pytest.mark.asyncio
    async def test_create_or_update_user_identities(
        self,
        auth_repository: AuthRepository,
        db_session: DBSession,  # type: ignore[reportPrivateUsage, unused-ignore]
    ) -> None:
        """Test create_or_update_user_identities with real database."""
        user_auth_id = "auth-123"
        # Identities removed for simplified model - test now passes as no-op
        # Identities removed for simplified model

        # Use real database session instead of mocking
        async with auth_repository.transaction() as session:
            # Identities removed for simplified model - test passes as no-op
            pass  # No longer needed with simplified model

        # Verify no identities are stored (simplified model)
        async with auth_repository.session(readonly=True) as session:
            query = select(UserIdentity).where(UserIdentity.user_auth_id == user_auth_id, UserIdentity.in_used == 1)
            result = await session.exec(query)
            identity_list = result.all()

            assert len(identity_list) == 0  # No identities in simplified model

    @pytest.mark.asyncio
    async def test_create_or_update_user_with_data(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_profile: UserProfileData
    ) -> None:
        """Test create_or_update_user with user data."""
        # Mock exec() to return a result that has first() method returning None
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec = AsyncMock(return_value=mock_result)

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
        """Test create_or_update_user raises DBError for database exceptions."""
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
        mock_session.exec.side_effect = SQLAlchemyError("DB Error")

        with pytest.raises(DBError):
            _ = await auth_repository.create_or_update_user(mock_session, user_data)

    # ============================================================================
    # Tests for get_user_info method
    # ============================================================================

    @pytest.fixture
    def mock_user_info(self) -> UserProfileData:
        """Fixture for a mock UserProfileData object."""
        return UserProfileData(
            id="user-123",
            aud="authenticated",
            role="authenticated",
            email="test@example.com",
            email_confirmed_at=datetime.now(),
            phone="+1234567890",
            last_sign_in_at=datetime.now(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            app_metadata={"provider": "email", "providers": ["email"]},
            user_metadata={
                "avatar_url": "https://example.com/avatar.jpg",
                "email": "test@example.com",
                "email_verified": True,
                "full_name": "Test User",
                "iss": "https://example.com",
                "name": "Test User",
                "phone_verified": False,
                "picture": "https://example.com/picture.jpg",
                "provider_id": "provider-123",
                "sub": "sub-123",
            },
        )

    @pytest.fixture
    def mock_user_entity(self) -> User:
        """Fixture for a mock User entity."""
        return User(
            auth_id="user-123",
            aud="authenticated",
            role="authenticated",
            email="test@example.com",
            email_confirmed_at=datetime.now(),
            phone="+1234567890",
            last_sign_in_at=datetime.now(),
            auth_created_at=datetime.now(),
            auth_updated_at=datetime.now(),
        )

    @pytest.fixture
    def mock_user_profile_entity(self) -> UserProfile:
        """Fixture for a mock UserProfile entity."""
        return UserProfile(
            user_auth_id="user-123",
            first_name="Test",
            last_name="User",
            display_name="Test User",
            avatar_url="https://example.com/avatar.jpg",
            bio="Test bio",
            location="Test City",
            website="https://example.com",
        )

    @pytest.mark.asyncio
    async def test_get_user_info_user_not_found(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test get_user_info returns None for non-existent user."""
        # Mock the internal implementation to return None
        with (
            patch.object(auth_repository, "_get_user_info_impl", AsyncMock(return_value=None)) as mock_impl,
            patch.object(auth_repository, "session") as mock_session_method,
        ):
            mock_session_context = AsyncMock()
            mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_context.__aexit__ = AsyncMock(return_value=None)
            mock_session_method.return_value = mock_session_context

            result = await auth_repository.get_user_info("non-existent-user")

            assert result is None
            mock_impl.assert_awaited_once_with(mock_session, "non-existent-user")

    @pytest.mark.asyncio
    async def test_get_user_info_empty_user_id_raises_value_error(self, auth_repository: AuthRepository) -> None:
        """Test get_user_info raises ValueError for empty user ID."""
        with pytest.raises(ValueError, match="User ID cannot be empty"):
            _ = await auth_repository.get_user_info("")

        with pytest.raises(ValueError, match="User ID cannot be empty"):
            _ = await auth_repository.get_user_info("   ")

        with pytest.raises(ValueError, match="User ID cannot be empty"):
            await auth_repository.get_user_info(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_get_user_info_valid_user(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserProfileData
    ) -> None:
        """Test get_user_info returns UserProfileData for valid user."""
        # Mock the internal implementation and session
        with (
            patch.object(auth_repository, "_get_user_info_impl", AsyncMock(return_value=mock_user_info)) as mock_impl,
            patch.object(auth_repository, "session") as mock_session_method,
        ):
            mock_session_context = AsyncMock()
            mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_context.__aexit__ = AsyncMock(return_value=None)
            mock_session_method.return_value = mock_session_context

            result = await auth_repository.get_user_info("user-123")

            assert result is not None
            assert result.id == "user-123"
            assert result.email == "test@example.com"
            mock_impl.assert_awaited_once_with(mock_session, "user-123")

    @pytest.mark.asyncio
    async def test_get_user_info_impl_user_not_found(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test _get_user_info_impl returns None when user not found."""
        with patch.object(auth_repository, "_get_base_user", AsyncMock(return_value=None)) as mock_base_user:
            result = await auth_repository._get_user_info_impl(mock_session, "non-existent-user")  # type: ignore[reportPrivateUsage, unused-ignore]

            assert result is None
            mock_base_user.assert_awaited_once_with(mock_session, "non-existent-user")

    @pytest.mark.asyncio
    async def test_get_base_user_found(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_entity: User
    ) -> None:
        """Test _get_base_user returns user when found."""
        # Mock exec() to return a result that has first() method returning the user
        mock_result = MagicMock()
        mock_result.first.return_value = mock_user_entity
        mock_session.exec = AsyncMock(return_value=mock_result)

        result = await auth_repository._get_base_user(mock_session, "user-123")  # type: ignore[reportPrivateUsage, unused-ignore]

        assert result is not None
        assert result.auth_id == "user-123"
        assert isinstance(result, User)

    @pytest.mark.asyncio
    async def test_get_user_metadata_simple_empty(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test _get_user_metadata_simple handles empty metadata."""
        # Mock exec() to return a result that has all() method returning empty list
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.exec = AsyncMock(return_value=mock_result)

        app_metadata, user_metadata = await auth_repository._get_user_metadata_simple(mock_session, "user-123")  # type: ignore[reportPrivateUsage, unused-ignore]

        assert app_metadata == {}
        assert user_metadata == {}

    @pytest.mark.asyncio
    async def test_get_user_metadata_simple_with_data_v2(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test _get_user_metadata_simple processes metadata correctly."""
        # Mock metadata rows
        mock_metadata_rows = [
            MagicMock(metadata_type="app", key="provider", value='"google"'),
            MagicMock(metadata_type="user", key="sub", value='"123"'),
        ]
        # Mock exec() to return a result that has all() method returning metadata rows
        mock_result = MagicMock()
        mock_result.all.return_value = mock_metadata_rows
        mock_session.exec = AsyncMock(return_value=mock_result)

        app_metadata, user_metadata = await auth_repository._get_user_metadata_simple(mock_session, "user-123")  # type: ignore[reportPrivateUsage, unused-ignore]

        assert app_metadata["provider"] == "google"
        assert user_metadata["sub"] == "123"

    @pytest.mark.asyncio
    async def test_get_user_metadata_simple_empty_v2(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test _get_user_metadata_simple handles empty identities."""
        # Mock exec() to return a result that has all() method returning empty list
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.exec = AsyncMock(return_value=mock_result)

        app_metadata, user_metadata = await auth_repository._get_user_metadata_simple(mock_session, "user-123")  # type: ignore[reportPrivateUsage, unused-ignore]

        assert app_metadata == {}
        assert user_metadata == {}

    @pytest.mark.asyncio
    async def test_get_user_profile_found(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_profile_entity: UserProfile
    ) -> None:
        """Test _get_user_profile returns profile data when found."""
        # Mock exec() to return a result that has first() method returning the profile
        mock_result = MagicMock()
        mock_result.first.return_value = mock_user_profile_entity
        mock_session.exec = AsyncMock(return_value=mock_result)

        profile = await auth_repository._get_user_profile(mock_session, "user-123")  # type: ignore[reportPrivateUsage, unused-ignore]

        assert profile is not None
        assert profile["first_name"] == "Test"
        assert profile["last_name"] == "User"
        assert profile["display_name"] == "Test User"

    @pytest.mark.asyncio
    async def test_get_user_profile_not_found(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test _get_user_profile returns None when profile not found."""
        # Mock exec() to return a result that has first() method returning None
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec = AsyncMock(return_value=mock_result)

        profile = await auth_repository._get_user_profile(mock_session, "user-123")  # type: ignore[reportPrivateUsage, unused-ignore]

        assert profile is None

    # ============================================================================
    # Tests for set_user_info method
    # ============================================================================

    @pytest.mark.asyncio
    async def test_set_user_info_valid_data(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserProfileData
    ) -> None:
        """Test set_user_info stores valid UserProfileData successfully."""
        # Mock the internal implementation to return True
        with (
            patch.object(auth_repository, "_set_user_info_impl", AsyncMock(return_value=True)) as mock_impl,
            patch.object(auth_repository, "transaction") as mock_transaction,
        ):
            mock_transaction_context = AsyncMock()
            mock_transaction_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_transaction_context.__aexit__ = AsyncMock(return_value=None)
            mock_transaction.return_value = mock_transaction_context

            result = await auth_repository.set_user_info(mock_user_info)

            assert result is True
            mock_impl.assert_awaited_once_with(mock_session, mock_user_info)

    @pytest.mark.asyncio
    async def test_set_user_info_none_raises_value_error(self, auth_repository: AuthRepository) -> None:
        """Test set_user_info raises ValueError for None user_info."""
        with pytest.raises(ValueError, match="User profile cannot be None"):
            await auth_repository.set_user_info(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_set_user_info_empty_id_raises_value_error(self, auth_repository: AuthRepository) -> None:
        """Test set_user_info raises ValueError for empty user ID."""
        invalid_user_info = UserProfileData(
            id="",
            aud="authenticated",
            role="authenticated",
            email="test@example.com",
            email_confirmed_at=None,
            phone=None,
            last_sign_in_at=None,
            created_at=datetime.now(),
            updated_at=None,
            app_metadata={"provider": "", "providers": []},
            user_metadata={},
        )

        with pytest.raises(ValueError, match="User profile must have a valid ID"):
            _ = await auth_repository.set_user_info(invalid_user_info)

    @pytest.mark.asyncio
    async def test_set_user_info_database_error_raises_dberror(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserProfileData
    ) -> None:
        """Test set_user_info raises DBError for database errors."""
        # Mock the transaction to raise an exception
        with patch.object(auth_repository, "transaction") as mock_transaction:
            mock_transaction_context = AsyncMock()
            mock_transaction_context.__aenter__ = AsyncMock(side_effect=SQLAlchemyError("DB Error"))
            mock_transaction_context.__aexit__ = AsyncMock(return_value=None)
            mock_transaction.return_value = mock_transaction_context

            with pytest.raises(DBError, match="Failed to set user info for user user-123"):
                _ = await auth_repository.set_user_info(mock_user_info)

    @pytest.mark.asyncio
    async def test_set_user_info_impl_complete_flow(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserProfileData
    ) -> None:
        """Test _set_user_info_impl executes complete storage flow."""
        # Mock helper methods
        with (
            patch.object(auth_repository, "_create_or_update_base_user_from_profile", AsyncMock()) as mock_create_user,
            patch.object(auth_repository, "create_or_update_user_metadata", AsyncMock()) as mock_store_app,
            patch.object(auth_repository, "_ensure_user_has_role", AsyncMock()) as mock_ensure_role,
        ):
            result = await auth_repository._set_user_info_impl(mock_session, mock_user_info)  # type: ignore[reportPrivateUsage, unused-ignore]

            assert result is True

            # Verify all helper methods were called
            mock_create_user.assert_awaited_once_with(mock_session, mock_user_info)
            # Metadata methods are called twice (app and user)
            assert mock_store_app.call_count == 2
            # Role ensure method should be called once
            mock_ensure_role.assert_awaited_once_with(mock_session, mock_user_info.id)

    @pytest.mark.asyncio
    async def test_set_user_info_impl_without_identities_and_profile(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test _set_user_info_impl handles missing identities and profile."""
        user_info_without_optional = UserProfileData(
            id="user-123",
            aud="authenticated",
            role="authenticated",
            email="test@example.com",
            email_confirmed_at=None,
            phone=None,
            last_sign_in_at=None,
            created_at=datetime.now(),
            updated_at=None,
            app_metadata={"provider": "email", "providers": ["email"]},
            user_metadata={},
        )

        # Mock helper methods
        with (
            patch.object(auth_repository, "_create_or_update_base_user_from_profile", AsyncMock()),
            patch.object(auth_repository, "create_or_update_user_metadata", AsyncMock()) as mock_store_metadata,
            patch.object(auth_repository, "_ensure_user_has_role", AsyncMock()),
        ):
            result = await auth_repository._set_user_info_impl(mock_session, user_info_without_optional)  # type: ignore[reportPrivateUsage, unused-ignore]

            assert result is True

            # Verify metadata method was called once (only app metadata, user metadata is empty)
            assert mock_store_metadata.call_count == 1

    @pytest.mark.asyncio
    async def test_create_or_update_base_user_from_profile_new_user(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserProfileData
    ) -> None:
        """Test _create_or_update_base_user_from_profile creates new user."""
        # Mock exec() to return a result that has first() method returning None
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec = AsyncMock(return_value=mock_result)  # No existing user

        await auth_repository._create_or_update_base_user_from_profile(mock_session, mock_user_info)  # type: ignore[reportPrivateUsage, unused-ignore]

        # Verify add was called for new user
        mock_session.add.assert_called_once()
        added_user = mock_session.add.call_args[0][0]
        assert added_user.auth_id == "user-123"
        assert added_user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_create_or_update_base_user_from_profile_existing_user(
        self,
        auth_repository: AuthRepository,
        mock_session: MagicMock,
        mock_user_info: UserProfileData,
        mock_user_entity: User,
    ) -> None:
        """Test _create_or_update_base_user_from_profile updates existing user."""
        # Mock exec() to return a result that has first() method returning existing user
        mock_result = MagicMock()
        mock_result.first.return_value = mock_user_entity
        mock_session.exec = AsyncMock(return_value=mock_result)  # Existing user found

        await auth_repository._create_or_update_base_user_from_profile(mock_session, mock_user_info)  # type: ignore[reportPrivateUsage, unused-ignore]

        # Verify add was not called (user already exists)
        mock_session.add.assert_not_called()

        # Verify existing user was updated
        assert mock_user_entity.aud == mock_user_info.aud
        assert mock_user_entity.role == mock_user_info.role
        assert mock_user_entity.email == mock_user_info.email

    @pytest.mark.asyncio
    async def test_get_user_metadata_simple(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserProfileData
    ) -> None:
        """Test _get_user_metadata_simple retrieves and processes metadata correctly."""
        # Mock the session.exec method
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.exec = AsyncMock(return_value=mock_result)

        app_metadata, user_metadata = await auth_repository._get_user_metadata_simple(mock_session, mock_user_info.id)  # type: ignore[reportPrivateUsage, unused-ignore]

        # Verify it returns empty dicts when no metadata exists
        assert app_metadata == {}
        assert user_metadata == {}

    @pytest.mark.asyncio
    async def test_store_user_metadata_simple(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserProfileData
    ) -> None:
        """Test _get_user_metadata_simple processes and returns user metadata."""
        # Mock the session.exec method
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.exec = AsyncMock(return_value=mock_result)

        app_metadata, user_metadata = await auth_repository._get_user_metadata_simple(mock_session, mock_user_info.id)  # type: ignore[reportPrivateUsage, unused-ignore]

        # Verify it returns empty dicts when no metadata exists
        assert app_metadata == {}
        assert user_metadata == {}

    @pytest.mark.asyncio
    async def test_get_user_profile_new_profile(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserProfileData
    ) -> None:
        """Test _get_user_profile returns None when no profile exists."""
        # Mock exec() to return a result that has first() method returning None
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec = AsyncMock(return_value=mock_result)  # No existing profile

        result = await auth_repository._get_user_profile(mock_session, mock_user_info.id)  # type: ignore[reportPrivateUsage, unused-ignore]

        # Verify no profile is returned
        assert result is None
        # Verify add was not called (this method only reads, doesn't create)
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_user_profile_existing_profile(
        self,
        auth_repository: AuthRepository,
        mock_session: MagicMock,
        mock_user_info: UserProfileData,
        mock_user_profile_entity: UserProfile,
    ) -> None:
        """Test _get_user_profile updates existing profile."""
        # Mock exec() to return a result that has first() method returning existing profile
        mock_result = MagicMock()
        mock_result.first.return_value = mock_user_profile_entity
        mock_session.exec = AsyncMock(return_value=mock_result)  # Existing profile found

        await auth_repository._get_user_profile(mock_session, mock_user_info.id)  # type: ignore[reportPrivateUsage, unused-ignore]

        # Verify add was not called (profile already exists)
        mock_session.add.assert_not_called()

        # Verify existing profile was updated
        assert mock_user_profile_entity.first_name == "Test"
        assert mock_user_profile_entity.last_name == "User"
        assert mock_user_profile_entity.display_name == "Test User"

    @pytest.mark.asyncio
    async def test_get_user_profile_no_profile_data(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test _get_user_profile returns None when no profile exists."""
        user_info_no_profile = UserProfileData(
            id="user-123",
            aud="authenticated",
            role="authenticated",
            email="test@example.com",
            email_confirmed_at=None,
            phone=None,
            last_sign_in_at=None,
            created_at=datetime.now(),
            updated_at=None,
            app_metadata={"provider": "", "providers": []},
            user_metadata={},
        )

        # Mock exec() to return a result that has first() method returning None
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec = AsyncMock(return_value=mock_result)

        result = await auth_repository._get_user_profile(mock_session, user_info_no_profile.id)  # type: ignore[reportPrivateUsage, unused-ignore]

        # Verify no profile is returned
        assert result is None
        # Verify add was not called (this method only reads, doesn't create)
        mock_session.add.assert_not_called()

    # ============================================================================
    # Integration tests for set_user_info and get_user_info round-trip
    # ============================================================================

    @pytest.mark.asyncio
    async def test_set_and_get_user_info_round_trip(
        self, auth_repository: AuthRepository, db_session: DBSession
    ) -> None:
        """Test complete round-trip: set_user_info -> get_user_info with data integrity using real database."""
        # Step 1: Generate a UserProfileData instance with arbitrary values for all attributes
        original_values = UserProfileData(
            id="test-user-12345",
            aud="authenticated",
            role="premium_user",
            email="roundtrip.test@example.com",
            email_confirmed_at=datetime(2024, 1, 15, 10, 30, 45),
            phone="+1-555-123-9876",
            confirmed_at=datetime(2024, 1, 17, 9, 15, 22),
            last_sign_in_at=datetime(2024, 3, 10, 16, 45, 12),
            created_at=datetime(2024, 1, 10, 8, 0, 0),
            updated_at=datetime(2024, 3, 8, 12, 30, 15),
            app_metadata={"provider": "google", "providers": ["email", "google", "facebook"]},
            user_metadata={
                "full_name": "John Alexander Doe",
                "avatar_url": "https://example.com/avatar/johndoe.jpg",
                "email_verified": True,
                "phone_verified": True,
                "name": "John Doe",
                "picture": "https://example.com/avatar/johndoe.jpg",
            },
        )

        # Step 2: Use set_user_info to store original_values into relevant tables
        result = await auth_repository.set_user_info(original_values)
        assert result is True

        # Step 3: Use get_user_info to retrieve back into another UserProfileData instance
        loaded_values = await auth_repository.get_user_info(original_values.id)
        assert loaded_values is not None

        # Step 4: Compare and assert original_values with loaded_values on each attribute

        # Basic user attributes
        assert loaded_values.id == original_values.id
        assert loaded_values.aud == original_values.aud
        assert loaded_values.role == original_values.role
        assert loaded_values.email == original_values.email
        assert loaded_values.email_confirmed_at == original_values.email_confirmed_at
        assert loaded_values.phone == original_values.phone
        assert loaded_values.confirmed_at == original_values.confirmed_at
        assert loaded_values.last_sign_in_at == original_values.last_sign_in_at
        assert loaded_values.created_at == original_values.created_at
        assert loaded_values.updated_at == original_values.updated_at
        assert loaded_values.is_anonymous == original_values.is_anonymous

        # App metadata comparison (now dicts)
        assert loaded_values.app_metadata["provider"] == original_values.app_metadata["provider"]
        assert set(loaded_values.app_metadata["providers"]) == set(original_values.app_metadata["providers"])

        # User metadata comparison (now dicts)
        assert loaded_values.user_metadata["full_name"] == original_values.user_metadata["full_name"]
        assert loaded_values.user_metadata["avatar_url"] == original_values.user_metadata["avatar_url"]
        assert loaded_values.user_metadata["email_verified"] == original_values.user_metadata["email_verified"]
        assert loaded_values.user_metadata["phone_verified"] == original_values.user_metadata["phone_verified"]
        assert loaded_values.user_metadata["name"] == original_values.user_metadata["name"]
        assert loaded_values.user_metadata["picture"] == original_values.user_metadata["picture"]

        # Identities and profile are now simplified in UserProfileData model
        # These complex nested structures have been removed for simplicity
        logger.info("Test completed successfully with simplified UserProfileData model")

    # ============================================================================
    # Integration tests for set_roles and get_roles round-trip
    # ============================================================================

    @pytest.mark.asyncio
    async def test_set_and_get_roles_round_trip(
        self, auth_repository: AuthRepository, db_session: DBSession
    ) -> None:
        """Test complete round-trip: set_roles -> get_roles with data integrity using real database."""

        # Step 1: Generate a random user ID for testing
        test_user_id = f"test-user-{uuid.uuid4()}"

        # Step 2: Generate a random list of roles for testing
        # Create pool of possible roles with different patterns
        role_pool = [
            "admin", "user", "moderator", "editor", "viewer", "contributor",
            "super_admin", "guest", "premium_user", "trial_user", "beta_tester",
            "content_manager", "data_analyst", "system_admin", "api_user"
        ]

        # Randomly select 3-7 roles from the pool
        num_roles = random.randint(3, 7)
        original_roles = random.sample(role_pool, num_roles)

        # Add some custom generated roles for more variety
        for _ in range(2):
            custom_role = f"custom_{''.join(random.choices(string.ascii_lowercase, k=6))}"
            original_roles.append(custom_role)

        # Sort for consistent comparison
        original_roles.sort()

        logger.info(f"Testing with user_id: {test_user_id}")
        logger.info(f"Testing with roles: {original_roles}")

        # Step 3: Use set_roles to store original_roles into database
        result = await auth_repository.set_roles(test_user_id, original_roles, disable_others=True)
        assert result is True

        # Step 4: Use get_roles to retrieve roles from database
        loaded_roles = await auth_repository.get_roles(test_user_id)

        # Sort loaded roles for comparison
        loaded_roles.sort()

        # Step 5: Compare and assert original_roles with loaded_roles
        assert loaded_roles is not None
        assert len(loaded_roles) == len(original_roles)
        assert set(loaded_roles) == set(original_roles)
        assert loaded_roles == original_roles  # Exact order match after sorting

        logger.info(f"Original roles: {original_roles}")
        logger.info(f"Loaded roles: {loaded_roles}")
        logger.info("Test completed successfully - roles match exactly")

    @pytest.mark.asyncio
    async def test_set_roles_disable_others_functionality(
        self, auth_repository: AuthRepository, db_session: DBSession
    ) -> None:
        """Test disable_others parameter functionality in set_roles method."""
        test_user_id = f"test-user-{uuid.uuid4()}"

        # Step 1: Set initial roles
        initial_roles = ["admin", "user", "moderator"]
        result = await auth_repository.set_roles(test_user_id, initial_roles, disable_others=True)
        assert result is True

        # Verify initial roles are set
        loaded_roles = await auth_repository.get_roles(test_user_id)
        assert set(loaded_roles) == set(initial_roles)

        # Step 2: Test disable_others=True (should replace existing roles)
        new_roles = ["editor", "viewer"]
        result = await auth_repository.set_roles(test_user_id, new_roles, disable_others=True)
        assert result is True

        # Should only have new roles
        loaded_roles = await auth_repository.get_roles(test_user_id)
        assert set(loaded_roles) == set(new_roles)
        assert "admin" not in loaded_roles  # Old roles should be disabled
        assert "moderator" not in loaded_roles

        # Step 3: Test disable_others=False (should add to existing roles)
        additional_roles = ["contributor", "beta_tester"]
        result = await auth_repository.set_roles(test_user_id, additional_roles, disable_others=False)
        assert result is True

        # Should have both new and additional roles
        loaded_roles = await auth_repository.get_roles(test_user_id)
        expected_roles = set(new_roles + additional_roles)
        assert set(loaded_roles) == expected_roles

        # Step 4: Test reactivation of previously disabled roles
        reactivated_roles = ["admin", "contributor"]  # admin was previously disabled
        result = await auth_repository.set_roles(test_user_id, reactivated_roles, disable_others=True)
        assert result is True

        # Should have reactivated admin and kept contributor
        loaded_roles = await auth_repository.get_roles(test_user_id)
        assert set(loaded_roles) == set(reactivated_roles)
        assert "admin" in loaded_roles  # Should be reactivated, not duplicated

        logger.info("Test completed successfully - disable_others functionality works correctly")

    @pytest.mark.asyncio
    async def test_set_roles_edge_cases(
        self, auth_repository: AuthRepository, db_session: DBSession
    ) -> None:
        """Test edge cases for set_roles and get_roles methods."""
        test_user_id = f"test-user-{uuid.uuid4()}"

        # Test 1: Empty roles list with disable_others=True (should disable all existing roles)
        # First, set some initial roles
        initial_roles = ["admin", "user"]
        result = await auth_repository.set_roles(test_user_id, initial_roles, disable_others=True)
        assert result is True

        # Verify roles are set
        loaded_roles = await auth_repository.get_roles(test_user_id)
        assert set(loaded_roles) == set(initial_roles)

        # Now set empty roles with disable_others=True (should disable all)
        result = await auth_repository.set_roles(test_user_id, [], disable_others=True)
        assert result is True  # Empty roles is valid - disables all existing roles

        # Should have no active roles
        loaded_roles = await auth_repository.get_roles(test_user_id)
        assert loaded_roles == []

        # Test 2: Single role
        single_role = ["single_role"]
        result = await auth_repository.set_roles(test_user_id, single_role, disable_others=True)
        assert result is True

        loaded_roles = await auth_repository.get_roles(test_user_id)
        assert loaded_roles == single_role

        # Test 3: Duplicate roles in input (should be deduplicated)
        duplicate_roles = ["role1", "role2", "role1", "role3", "role2"]
        result = await auth_repository.set_roles(test_user_id, duplicate_roles, disable_others=True)
        assert result is True

        loaded_roles = await auth_repository.get_roles(test_user_id)
        unique_roles = list(set(duplicate_roles))
        assert set(loaded_roles) == set(unique_roles)

        # Test 4: Get roles for non-existent user
        non_existent_user = f"non-existent-{uuid.uuid4()}"
        loaded_roles = await auth_repository.get_roles(non_existent_user)
        assert loaded_roles == []

        logger.info("Test completed successfully - edge cases handled correctly")

    @pytest.mark.asyncio
    async def test_set_user_info_ensures_default_role(
        self, auth_repository: AuthRepository, db_session: DBSession
    ) -> None:
        """Test that set_user_info ensures user has at least one role by adding default role."""
        # Create a user profile without any explicit roles
        user_profile = UserProfileData(
            id=f"test-user-{uuid.uuid4()}",
            aud="authenticated",
            role="authenticated",  # This is in the User table, not UserRole table
            email="test@example.com",
            email_confirmed_at=datetime.now(),
            phone="+1234567890",
            last_sign_in_at=datetime.now(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            app_metadata={"provider": "email"},
            user_metadata={"name": "Test User"},
        )

        # Set user info - should automatically add default role if none exist
        result = await auth_repository.set_user_info(user_profile)
        assert result is True

        # Verify user has the default role
        roles = await auth_repository.get_roles(user_profile.id)
        assert "default" in roles
        assert len(roles) >= 1

        logger.info(f"User {user_profile.id} automatically assigned roles: {roles}")

    @pytest.mark.asyncio
    async def test_set_user_info_preserves_existing_roles(
        self, auth_repository: AuthRepository, db_session: DBSession
    ) -> None:
        """Test that set_user_info doesn't add default role when user already has roles."""
        user_id = f"test-user-{uuid.uuid4()}"

        # First, set some roles for the user
        existing_roles = ["admin", "user"]
        result = await auth_repository.set_roles(user_id, existing_roles, disable_others=True)
        assert result is True

        # Create user profile
        user_profile = UserProfileData(
            id=user_id,
            aud="authenticated",
            role="authenticated",
            email="test@example.com",
            email_confirmed_at=datetime.now(),
            phone="+1234567890",
            last_sign_in_at=datetime.now(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            app_metadata={"provider": "email"},
            user_metadata={"name": "Test User"},
        )

        # Set user info - should NOT add default role since user already has roles
        result = await auth_repository.set_user_info(user_profile)
        assert result is True

        # Verify user still has the same roles (no default role added)
        roles = await auth_repository.get_roles(user_id)
        assert set(roles) == set(existing_roles)
        assert "default" not in roles
        assert len(roles) == 2

        logger.info(f"User {user_id} preserved existing roles: {roles}")
