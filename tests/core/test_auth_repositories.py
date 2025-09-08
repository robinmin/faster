from datetime import datetime
import json
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select

from faster.core.auth.models import (
    AppMetadata,
    UserIdentityData,
    UserInfo,
    UserMetadata,
    UserProfileData,
)
from faster.core.auth.repositories import AuthRepository
from faster.core.auth.schemas import User, UserIdentity, UserProfile
from faster.core.auth.schemas import UserMetadata as UserMetadataSchema
from faster.core.database import DBSession
from faster.core.exceptions import DBError


class TestAuthRepository:
    """Test AuthRepository class."""

    @pytest.fixture
    def auth_repository(self) -> AuthRepository:
        """Create AuthRepository instance."""
        return AuthRepository()

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
    async def test_create_or_update_user_metadata(
        self, auth_repository: AuthRepository, db_session: DBSession
    ) -> None:
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
                UserMetadataSchema.in_used == 1
            )
            result = await session.exec(query)
            metadata_list = result.all()

            assert len(metadata_list) == 2
            stored_keys = {m.key for m in metadata_list}
            assert stored_keys == {"key1", "key2"}

    @pytest.mark.asyncio
    async def test_create_or_update_user_identities(
        self, auth_repository: AuthRepository, db_session: DBSession  # type: ignore[reportPrivateUsage, unused-ignore]
    ) -> None:
        """Test create_or_update_user_identities with real database."""
        user_auth_id = "auth-123"
        identities = [
            UserIdentityData(
                identity_id=str(uuid.uuid4()),
                id="provider-user-1",
                user_id=user_auth_id,
                identity_data={"sub": "123", "email": "test@example.com"},
                provider="google",
                last_sign_in_at=datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        ]

        # Use real database session instead of mocking
        async with auth_repository.transaction() as session:
            await auth_repository.create_or_update_user_identities(session, user_auth_id, identities)

        # Verify identity was stored correctly by querying the database
        async with auth_repository.session(readonly=True) as session:
            query = select(UserIdentity).where(
                UserIdentity.user_auth_id == user_auth_id,
                UserIdentity.in_used == 1
            )
            result = await session.exec(query)
            identity_list = result.all()

            assert len(identity_list) == 1
            stored_identity = identity_list[0]
            assert stored_identity.provider == "google"
            assert stored_identity.provider_user_id == "provider-user-1"
            # Verify JSON serialization of identity_data
            assert stored_identity.identity_data is not None
            assert json.loads(stored_identity.identity_data) == {"sub": "123", "email": "test@example.com"}

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
    def mock_user_info(self) -> UserInfo:
        """Fixture for a mock UserInfo object."""
        return UserInfo(
            id="user-123",
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
            app_metadata=AppMetadata(provider="email", providers=["email"]),
            user_metadata=UserMetadata(
                avatar_url="https://example.com/avatar.jpg",
                email="test@example.com",
                email_verified=True,
                full_name="Test User",
                iss="https://example.com",
                name="Test User",
                phone_verified=False,
                picture="https://example.com/picture.jpg",
                provider_id="provider-123",
                sub="sub-123",
            ),
            identities=[
                UserIdentityData(
                    identity_id="identity-123",
                    id="provider-user-123",
                    user_id="user-123",
                    identity_data={"sub": "123"},
                    provider="google",
                    last_sign_in_at=datetime.now(),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
            ],
            profile={
                "first_name": "Test",
                "last_name": "User",
                "display_name": "Test User",
                "avatar_url": "https://example.com/avatar.jpg",
                "bio": "Test bio",
                "location": "Test City",
                "website": "https://example.com",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
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
            confirmed_at=datetime.now(),
            last_sign_in_at=datetime.now(),
            is_anonymous=False,
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
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserInfo
    ) -> None:
        """Test get_user_info returns UserInfo for valid user."""
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
    async def test_get_base_user_not_found(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test _get_base_user returns None when user not found."""
        # Mock exec() to return a result that has first() method returning None
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec = AsyncMock(return_value=mock_result)

        result = await auth_repository._get_base_user(mock_session, "non-existent-user")  # type: ignore[reportPrivateUsage, unused-ignore]

        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_metadata_with_data(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test _get_user_metadata processes metadata correctly."""
        # Mock metadata rows
        mock_metadata_rows = [
            MagicMock(metadata_type="app", key="provider", value='"email"'),
            MagicMock(metadata_type="app", key="providers", value='["email", "google"]'),
            MagicMock(metadata_type="user", key="full_name", value='"Test User"'),
            MagicMock(metadata_type="user", key="email_verified", value="true"),
        ]
        # Mock exec() to return a result that has all() method returning metadata rows
        mock_result = MagicMock()
        mock_result.all.return_value = mock_metadata_rows
        mock_session.exec = AsyncMock(return_value=mock_result)

        app_metadata, user_metadata = await auth_repository._get_user_metadata(mock_session, "user-123")  # type: ignore[reportPrivateUsage, unused-ignore]

        assert app_metadata.provider == "email"
        assert app_metadata.providers == ["email", "google"]
        assert user_metadata.full_name == "Test User"
        assert user_metadata.email_verified is True

    @pytest.mark.asyncio
    async def test_get_user_metadata_empty(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test _get_user_metadata handles empty metadata."""
        # Mock exec() to return a result that has all() method returning empty list
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.exec = AsyncMock(return_value=mock_result)

        app_metadata, user_metadata = await auth_repository._get_user_metadata(mock_session, "user-123")  # type: ignore[reportPrivateUsage, unused-ignore]

        assert app_metadata.provider == ""
        assert app_metadata.providers == []
        assert user_metadata.full_name is None

    @pytest.mark.asyncio
    async def test_get_user_identities_with_data(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test _get_user_identities processes identities correctly."""
        mock_identity_row = MagicMock(
            identity_id="identity-123",
            provider_user_id="provider-user-123",
            provider="google",
            last_sign_in_at=datetime.now(),
            identity_created_at=datetime.now(),
            identity_updated_at=datetime.now(),
            identity_data='{"sub": "123"}',
        )
        # Mock exec() to return a result that has all() method returning identity rows
        mock_result = MagicMock()
        mock_result.all.return_value = [mock_identity_row]
        mock_session.exec = AsyncMock(return_value=mock_result)

        identities = await auth_repository._get_user_identities(mock_session, "user-123")  # type: ignore[reportPrivateUsage, unused-ignore]

        assert len(identities) == 1
        assert identities[0].identity_id == "identity-123"
        assert identities[0].provider == "google"
        assert identities[0].identity_data == {"sub": "123"}

    @pytest.mark.asyncio
    async def test_get_user_identities_empty(self, auth_repository: AuthRepository, mock_session: MagicMock) -> None:
        """Test _get_user_identities handles empty identities."""
        # Mock exec() to return a result that has all() method returning empty list
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.exec = AsyncMock(return_value=mock_result)

        identities = await auth_repository._get_user_identities(mock_session, "user-123")  # type: ignore[reportPrivateUsage, unused-ignore]

        assert identities == []

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
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserInfo
    ) -> None:
        """Test set_user_info stores valid UserInfo successfully."""
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
        with pytest.raises(ValueError, match="User info cannot be None"):
            await auth_repository.set_user_info(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_set_user_info_empty_id_raises_value_error(self, auth_repository: AuthRepository) -> None:
        """Test set_user_info raises ValueError for empty user ID."""
        invalid_user_info = UserInfo(
            id="",
            aud="authenticated",
            role="authenticated",
            email="test@example.com",
            email_confirmed_at=None,
            phone=None,
            confirmed_at=None,
            last_sign_in_at=None,
            is_anonymous=False,
            created_at=None,
            updated_at=None,
            app_metadata=AppMetadata(provider="", providers=[]),
            user_metadata=UserMetadata(),
            identities=[],
            profile=None,
        )

        with pytest.raises(ValueError, match="User info must have a valid ID"):
            _ = await auth_repository.set_user_info(invalid_user_info)

    @pytest.mark.asyncio
    async def test_set_user_info_database_error_raises_dberror(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserInfo
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
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserInfo
    ) -> None:
        """Test _set_user_info_impl executes complete storage flow."""
        # Mock helper methods
        with (
            patch.object(auth_repository, "_create_or_update_base_user", AsyncMock()) as mock_create_user,
            patch.object(auth_repository, "_store_app_metadata", AsyncMock()) as mock_store_app,
            patch.object(auth_repository, "_store_user_metadata", AsyncMock()) as mock_store_user,
            patch.object(auth_repository, "create_or_update_user_identities", AsyncMock()) as mock_store_identities,
            patch.object(auth_repository, "_store_user_profile", AsyncMock()) as mock_store_profile,
        ):
            result = await auth_repository._set_user_info_impl(mock_session, mock_user_info)  # type: ignore[reportPrivateUsage, unused-ignore]

            assert result is True

            # Verify all helper methods were called
            mock_create_user.assert_awaited_once_with(mock_session, mock_user_info)
            mock_store_app.assert_awaited_once_with(mock_session, mock_user_info)
            mock_store_user.assert_awaited_once_with(mock_session, mock_user_info)
            mock_store_identities.assert_awaited_once_with(mock_session, mock_user_info.id, mock_user_info.identities)
            mock_store_profile.assert_awaited_once_with(mock_session, mock_user_info)

    @pytest.mark.asyncio
    async def test_set_user_info_impl_without_identities_and_profile(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test _set_user_info_impl handles missing identities and profile."""
        user_info_without_optional = UserInfo(
            id="user-123",
            aud="authenticated",
            role="authenticated",
            email="test@example.com",
            email_confirmed_at=None,
            phone=None,
            confirmed_at=None,
            last_sign_in_at=None,
            is_anonymous=False,
            created_at=None,
            updated_at=None,
            app_metadata=AppMetadata(provider="email", providers=["email"]),
            user_metadata=UserMetadata(),
            identities=[],  # Empty identities
            profile=None,  # No profile
        )

        # Mock helper methods
        with (
            patch.object(auth_repository, "_create_or_update_base_user", AsyncMock()),
            patch.object(auth_repository, "_store_app_metadata", AsyncMock()),
            patch.object(auth_repository, "_store_user_metadata", AsyncMock()),
            patch.object(auth_repository, "create_or_update_user_identities", AsyncMock()) as mock_store_identities,
            patch.object(auth_repository, "_store_user_profile", AsyncMock()) as mock_store_profile,
        ):
            result = await auth_repository._set_user_info_impl(mock_session, user_info_without_optional)  # type: ignore[reportPrivateUsage, unused-ignore]

            assert result is True

            # Verify identities and profile methods were not called
            mock_store_identities.assert_not_awaited()
            mock_store_profile.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_or_update_base_user_new_user(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserInfo
    ) -> None:
        """Test _create_or_update_base_user creates new user."""
        # Mock exec() to return a result that has first() method returning None
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec = AsyncMock(return_value=mock_result)  # No existing user

        await auth_repository._create_or_update_base_user(mock_session, mock_user_info)  # type: ignore[reportPrivateUsage, unused-ignore]

        # Verify add was called for new user
        mock_session.add.assert_called_once()
        added_user = mock_session.add.call_args[0][0]
        assert added_user.auth_id == "user-123"
        assert added_user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_create_or_update_base_user_existing_user(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserInfo, mock_user_entity: User
    ) -> None:
        """Test _create_or_update_base_user updates existing user."""
        # Mock exec() to return a result that has first() method returning existing user
        mock_result = MagicMock()
        mock_result.first.return_value = mock_user_entity
        mock_session.exec = AsyncMock(return_value=mock_result)  # Existing user found

        await auth_repository._create_or_update_base_user(mock_session, mock_user_info)  # type: ignore[reportPrivateUsage, unused-ignore]

        # Verify add was not called (user already exists)
        mock_session.add.assert_not_called()

        # Verify existing user was updated
        assert mock_user_entity.aud == mock_user_info.aud
        assert mock_user_entity.role == mock_user_info.role
        assert mock_user_entity.email == mock_user_info.email

    @pytest.mark.asyncio
    async def test_store_app_metadata(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserInfo
    ) -> None:
        """Test _store_app_metadata calls create_or_update_user_metadata."""
        with patch.object(auth_repository, "create_or_update_user_metadata", AsyncMock()) as mock_metadata:
            await auth_repository._store_app_metadata(mock_session, mock_user_info)  # type: ignore[reportPrivateUsage, unused-ignore]

            mock_metadata.assert_awaited_once()
            call_args = mock_metadata.call_args
            assert call_args[0][1] == "user-123"  # user_auth_id
            assert call_args[0][2] == "app"  # metadata_type
            assert "provider" in call_args[0][3]  # metadata dict

    @pytest.mark.asyncio
    async def test_store_user_metadata(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserInfo
    ) -> None:
        """Test _store_user_metadata processes and stores user metadata."""
        with patch.object(auth_repository, "create_or_update_user_metadata", AsyncMock()) as mock_metadata:
            await auth_repository._store_user_metadata(mock_session, mock_user_info)  # type: ignore[reportPrivateUsage, unused-ignore]

            mock_metadata.assert_awaited_once()
            call_args = mock_metadata.call_args
            assert call_args[0][1] == "user-123"  # user_auth_id
            assert call_args[0][2] == "user"  # metadata_type
            metadata_dict = call_args[0][3]
            assert "full_name" in metadata_dict
            assert "email_verified" in metadata_dict

    @pytest.mark.asyncio
    async def test_store_user_profile_new_profile(
        self, auth_repository: AuthRepository, mock_session: MagicMock, mock_user_info: UserInfo
    ) -> None:
        """Test _store_user_profile creates new profile."""
        # Mock exec() to return a result that has first() method returning None
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec = AsyncMock(return_value=mock_result)  # No existing profile

        await auth_repository._store_user_profile(mock_session, mock_user_info)  # type: ignore[reportPrivateUsage, unused-ignore]

        # Verify add was called for new profile
        mock_session.add.assert_called_once()
        added_profile = mock_session.add.call_args[0][0]
        assert added_profile.user_auth_id == "user-123"
        assert added_profile.first_name == "Test"

    @pytest.mark.asyncio
    async def test_store_user_profile_existing_profile(
        self,
        auth_repository: AuthRepository,
        mock_session: MagicMock,
        mock_user_info: UserInfo,
        mock_user_profile_entity: UserProfile,
    ) -> None:
        """Test _store_user_profile updates existing profile."""
        # Mock exec() to return a result that has first() method returning existing profile
        mock_result = MagicMock()
        mock_result.first.return_value = mock_user_profile_entity
        mock_session.exec = AsyncMock(return_value=mock_result)  # Existing profile found

        await auth_repository._store_user_profile(mock_session, mock_user_info)  # type: ignore[reportPrivateUsage, unused-ignore]

        # Verify add was not called (profile already exists)
        mock_session.add.assert_not_called()

        # Verify existing profile was updated
        assert mock_user_profile_entity.first_name == "Test"
        assert mock_user_profile_entity.last_name == "User"
        assert mock_user_profile_entity.display_name == "Test User"

    @pytest.mark.asyncio
    async def test_store_user_profile_no_profile_data(
        self, auth_repository: AuthRepository, mock_session: MagicMock
    ) -> None:
        """Test _store_user_profile handles None profile data."""
        user_info_no_profile = UserInfo(
            id="user-123",
            aud="authenticated",
            role="authenticated",
            email="test@example.com",
            email_confirmed_at=None,
            phone=None,
            confirmed_at=None,
            last_sign_in_at=None,
            is_anonymous=False,
            created_at=None,
            updated_at=None,
            app_metadata=AppMetadata(provider="", providers=[]),
            user_metadata=UserMetadata(),
            identities=[],
            profile=None,  # No profile data
        )

        # Mock exec() to return a result that has first() method returning None
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec = AsyncMock(return_value=mock_result)

        await auth_repository._store_user_profile(mock_session, user_info_no_profile)  # type: ignore[reportPrivateUsage, unused-ignore]

        # Should still create profile with None values
        mock_session.add.assert_called_once()
        added_profile = mock_session.add.call_args[0][0]
        assert added_profile.user_auth_id == "user-123"
        assert added_profile.first_name is None

    # ============================================================================
    # Integration tests for set_user_info and get_user_info round-trip
    # ============================================================================

    @pytest.mark.asyncio
    async def test_set_and_get_user_info_round_trip(
        self, auth_repository: AuthRepository, db_session: DBSession
    ) -> None:
        """Test complete round-trip: set_user_info -> get_user_info with data integrity using real database."""
        # Step 1: Generate a UserInfo instance with arbitrary values for all attributes
        original_values = UserInfo(
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
            is_anonymous=False,
            app_metadata=AppMetadata(
                provider="google",
                providers=["email", "google", "facebook"]
            ),
            user_metadata=UserMetadata(
                full_name="John Alexander Doe",
                avatar_url="https://example.com/avatar/johndoe.jpg",
                email_verified=True,
                phone_verified=True,
                name="John Doe",
                picture="https://example.com/avatar/johndoe.jpg"
            ),
            identities=[
                UserIdentityData(
                    identity_id="google-identity-789",
                    id="test-user-12345",
                    user_id="test-user-12345",
                    identity_data={"sub": "google-789", "email": "roundtrip.test@gmail.com"},
                    provider="google",
                    last_sign_in_at=datetime(2024, 3, 10, 16, 45, 12),
                    created_at=datetime(2024, 1, 15, 11, 0, 0),
                    updated_at=datetime(2024, 3, 8, 13, 15, 45)
                )
            ],
            profile={
                "first_name": "John",
                "last_name": "Doe",
                "display_name": "John Alexander Doe",
                "avatar_url": "https://example.com/avatar/johndoe.jpg",
                "website": "https://johndoe.dev",
                "bio": "Software engineer and tech enthusiast"
            }
        )

        # Step 2: Use set_user_info to store original_values into relevant tables
        result = await auth_repository.set_user_info(original_values)
        assert result is True

        # Step 3: Use get_user_info to retrieve back into another UserInfo instance
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

        # App metadata comparison
        assert loaded_values.app_metadata.provider == original_values.app_metadata.provider
        assert set(loaded_values.app_metadata.providers) == set(original_values.app_metadata.providers)

        # User metadata comparison
        assert loaded_values.user_metadata.full_name == original_values.user_metadata.full_name
        assert loaded_values.user_metadata.avatar_url == original_values.user_metadata.avatar_url
        assert loaded_values.user_metadata.email_verified == original_values.user_metadata.email_verified
        assert loaded_values.user_metadata.phone_verified == original_values.user_metadata.phone_verified
        assert loaded_values.user_metadata.name == original_values.user_metadata.name
        assert loaded_values.user_metadata.picture == original_values.user_metadata.picture

        # Identities comparison
        assert len(loaded_values.identities) == len(original_values.identities)
        loaded_identity = loaded_values.identities[0]
        original_identity = original_values.identities[0]
        assert loaded_identity.identity_id == original_identity.identity_id
        assert loaded_identity.provider == original_identity.provider
        assert loaded_identity.identity_data == original_identity.identity_data
        assert loaded_identity.last_sign_in_at == original_identity.last_sign_in_at
        assert loaded_identity.created_at == original_identity.created_at
        assert loaded_identity.updated_at == original_identity.updated_at

        # Profile comparison (dict type) - check that all original profile fields are present
        assert loaded_values.profile is not None
        assert original_values.profile is not None
        for key, value in original_values.profile.items():
            assert loaded_values.profile[key] == value
