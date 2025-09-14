from collections.abc import Callable
from datetime import datetime
import json
import logging
from typing import Any

from sqlmodel import select

from ..database import BaseRepository, DatabaseManager, DBSession
from ..exceptions import DBError
from .models import UserProfileData
from .schemas import User, UserAction, UserMetadata, UserProfile, UserRole

###############################################################################

logger = logging.getLogger(__name__)


class AuthRepository(BaseRepository):
    """
    Repository for authentication-related database operations.

    Handles user management, authentication metadata, user identities, and profiles
    using soft-delete patterns for data consistency. Provides comprehensive
    CRUD operations for all authentication-related entities.

    Inherits from BaseRepository for standard database operations and session management.
    """

    DEFAULT_ROLE = "default"

    def __init__(
        self, session_factory: Callable[[], DBSession] | None = None, db_manager: DatabaseManager | None = None
    ) -> None:
        """
        Initialize the repository with optional session factory and database manager.

        Args:
            session_factory: Optional async session factory function
            db_manager: Optional database manager instance (uses singleton if None)
        """
        # Initialize base repository
        super().__init__(db_manager)

        # Override session factory if provided
        if session_factory is not None:
            self.configure_session_factory(session_factory)

    async def find_by_criteria(self, criteria: dict[str, Any]) -> list[Any]:
        """
        Find authentication entities by criteria (placeholder implementation).

        Args:
            criteria: Search criteria dictionary

        Returns:
            Empty list (placeholder - implement based on specific needs)
        """
        async with self.session(readonly=True) as _:
            return []

    async def check_user_profile_exists(self, user_id: str) -> bool:
        """
        Check if a user profile exists for the given user ID.

        Args:
            user_id: The user's authentication ID

        Returns:
            True if profile exists, False otherwise

        Raises:
            DBError: If database query fails

        Example:
            >>> repo = AuthRepository()
            >>> exists = await repo.check_user_profile_exists("user123")
            >>> print(exists)  # True or False
        """
        if not user_id or not user_id.strip():
            raise ValueError("User ID cannot be empty")

        try:
            async with self.session(readonly=True) as session:
                return await self._check_user_profile_exists_impl(session, user_id)
        except Exception as e:
            logger.error(f"Failed to check user profile existence: {e}", extra={"user_id": user_id})
            raise DBError(f"Failed to check user profile existence for user {user_id}: {e}") from e

    async def _check_user_profile_exists_impl(self, session: DBSession, user_id: str) -> bool:
        """
        Internal implementation for checking user profile existence.

        Args:
            session: Database session
            user_id: User authentication ID

        Returns:
            True if profile exists, False otherwise
        """
        try:
            # Check for the existence of a user profile in the profiles table
            query = select(UserProfile).where(UserProfile.user_auth_id == user_id)
            result = await session.exec(query)
            profile = result.first()
            return profile is not None
        except Exception as e:
            logger.error(f"Database error checking user profile: {e}", extra={"user_id": user_id})
            raise

    async def get_user_by_auth_id(self, session: DBSession, auth_id: str) -> User | None:
        """
        Get user by authentication ID.

        Args:
            session: Database session
            auth_id: User's authentication ID

        Returns:
            User entity if found, None otherwise

        Raises:
            ValueError: If auth_id is empty
            DBError: If database query fails
        """
        if not auth_id or not auth_id.strip():
            raise ValueError("Authentication ID cannot be empty")

        try:
            query = select(User).where(User.auth_id == auth_id)
            result = await session.exec(query)
            return result.first()
        except Exception as e:
            logger.error(f"Error fetching user by auth_id {auth_id}: {e}")
            raise DBError(f"Failed to fetch user by auth_id {auth_id}: {e}") from e

    async def create_or_update_user(self, session: DBSession, user_data: dict[str, Any]) -> User:
        """
        Create or update user from user data using upsert pattern.

        Args:
            session: Database session
            user_data: Dictionary containing user data with required 'id' field

        Returns:
            User entity (created or updated)

        Raises:
            ValueError: If user_data is invalid or missing required fields
            DBError: If database operation fails

        Example:
            >>> user_data = {"id": "user123", "email": "test@example.com"}
            >>> user = await repo.create_or_update_user(session, user_data)
        """
        if not user_data:
            raise ValueError("User data cannot be empty")
        if "id" not in user_data or not user_data["id"]:
            raise ValueError("User data must contain a valid 'id' field")

        try:
            query = select(User).where(User.auth_id == user_data["id"])
            result = await session.exec(query)
            existing_user = result.first()

            user: User
            if existing_user:
                # Update existing user
                existing_user.aud = user_data.get("aud", "")
                existing_user.role = user_data.get("role", "")
                existing_user.email = user_data.get("email", "")
                existing_user.email_confirmed_at = user_data.get("email_confirmed_at")
                existing_user.phone = user_data.get("phone")
                existing_user.confirmed_at = user_data.get("confirmed_at")
                existing_user.last_sign_in_at = user_data.get("last_sign_in_at")
                existing_user.is_anonymous = user_data.get("is_anonymous", False)
                existing_user.auth_created_at = user_data.get("created_at")
                existing_user.auth_updated_at = user_data.get("updated_at")
                user = existing_user
            else:
                # Create new user
                user = User(
                    auth_id=user_data["id"],
                    aud=user_data.get("aud", ""),
                    role=user_data.get("role", ""),
                    email=user_data.get("email", ""),
                    email_confirmed_at=user_data.get("email_confirmed_at"),
                    phone=user_data.get("phone"),
                    confirmed_at=user_data.get("confirmed_at"),
                    last_sign_in_at=user_data.get("last_sign_in_at"),
                    is_anonymous=user_data.get("is_anonymous", False),
                    auth_created_at=user_data.get("created_at"),
                    auth_updated_at=user_data.get("updated_at"),
                )
                session.add(user)

            await session.flush()
            logger.info(
                f"{'Updated existing' if existing_user else 'Created new'} user with auth_id: {user_data['id']}"
            )
            return user
        except Exception as e:
            logger.error(f"Error creating or updating user for auth_id {user_data['id']}: {e}")
            raise DBError(f"Failed to create or update user for auth_id {user_data['id']}: {e}") from e

    async def create_or_update_user_metadata(
        self, session: DBSession, user_auth_id: str, metadata_type: str, metadata: dict[str, Any]
    ) -> None:
        """
        Create or update user metadata using soft delete pattern.

        First marks all existing metadata entries as inactive (in_used=0), then creates
        new entries with the provided metadata as active (in_used=1).

        Args:
            session: Database session
            user_auth_id: User's authentication ID (required, non-empty string)
            metadata_type: Type of metadata (e.g., 'app', 'user')
            metadata: Dictionary of metadata key-value pairs

        Raises:
            ValueError: If parameters are invalid
            DBError: If database operation fails

        Example:
            >>> metadata = {"theme": "dark", "lang": "en"}
            >>> await repo.create_or_update_user_metadata(session, "user123", "user", metadata)
        """
        if not user_auth_id or not user_auth_id.strip():
            raise ValueError("User auth ID cannot be empty")
        if not metadata_type or not metadata_type.strip():
            raise ValueError("Metadata type cannot be empty")
        if not metadata:
            raise ValueError("Metadata dictionary cannot be empty")

        try:
            # Handle each metadata key individually to avoid UNIQUE constraint violations
            for key, value in metadata.items():
                # First, try to find existing record for this specific key
                existing_query = select(UserMetadata).where(
                    UserMetadata.user_auth_id == user_auth_id,
                    UserMetadata.metadata_type == metadata_type,
                    UserMetadata.key == key,
                )
                existing_result = await session.exec(existing_query)
                existing_record = existing_result.first()

                if existing_record:
                    # Update existing record
                    existing_record.value = json.dumps(value) if value is not None else None
                    existing_record.in_used = 1
                    existing_record.updated_at = datetime.now()
                else:
                    # Insert new record
                    new_record = UserMetadata(
                        user_auth_id=user_auth_id,
                        metadata_type=metadata_type,
                        key=key,
                        value=json.dumps(value) if value is not None else None,
                    )
                    session.add(new_record)

            # Soft delete any remaining records that are no longer in the metadata
            existing_keys = set(metadata.keys())
            all_existing_query = select(UserMetadata).where(
                UserMetadata.user_auth_id == user_auth_id,
                UserMetadata.metadata_type == metadata_type,
                UserMetadata.in_used == 1,
            )
            all_existing_result = await session.exec(all_existing_query)

            for record in all_existing_result:
                if record.key not in existing_keys:
                    record.in_used = 0
                    record.updated_at = datetime.now()
        except Exception as e:
            logger.error(f"Error creating or updating metadata for user {user_auth_id}, type {metadata_type}: {e}")
            raise DBError(
                f"Failed to create or update metadata for user {user_auth_id}, type {metadata_type}: {e}"
            ) from e

    async def get_user_info(self, user_id: str, session: DBSession | None = None) -> UserProfileData | None:
        """
        Get user profile information from database.

        Args:
            user_id: User's authentication ID
            session: Optional database session to use (for background tasks)

        Returns:
            UserProfileData object if user exists, None otherwise

        Raises:
            ValueError: If user_id is empty
            DBError: If database query fails

        Example:
            >>> repo = AuthRepository()
            >>> user_profile = await repo.get_user_info("user123")
            >>> print(user_profile.email)  # user@example.com
        """
        if not user_id or not user_id.strip():
            raise ValueError("User ID cannot be empty")

        try:
            if session is not None:
                # Use provided session (for background tasks)
                return await self._get_user_info_impl(session, user_id)
            # Create new session (normal operation)
            async with self.session(readonly=True) as db_session:
                return await self._get_user_info_impl(db_session, user_id)
        except Exception as e:
            logger.error(f"Failed to get user info: {e}", extra={"user_id": user_id})
            raise DBError(f"Failed to get user info for user {user_id}: {e}") from e

    async def _get_user_info_impl(self, session: DBSession, user_id: str) -> UserProfileData | None:
        """
        Internal implementation for getting user profile information.

        Retrieves user data from the database and constructs a UserProfileData object.

        Args:
            session: Database session
            user_id: User's authentication ID

        Returns:
            UserProfileData object if user exists, None otherwise
        """
        try:
            # Get base user information
            user = await self._get_base_user(session, user_id)
            if not user:
                return None

            # Get and process metadata (simplified for compatibility)
            app_metadata, user_metadata = await self._get_user_metadata_simple(session, user_id)

            # Create UserProfileData object
            return UserProfileData(
                id=user.auth_id,
                aud=user.aud or "",
                role=user.role or "",
                email=user.email or "",
                email_confirmed_at=user.email_confirmed_at,
                phone=user.phone,
                confirmed_at=user.confirmed_at,
                last_sign_in_at=user.last_sign_in_at,
                is_anonymous=user.is_anonymous,
                created_at=user.auth_created_at or datetime.now(),
                updated_at=user.auth_updated_at,
                app_metadata=app_metadata,
                user_metadata=user_metadata,
                identities=[],  # Simplified - can be extended if needed
            )

        except Exception as e:
            logger.error(f"Error getting user info for user_id {user_id}: {e}")
            raise

    async def _get_base_user(self, session: DBSession, user_id: str) -> User | None:
        """Get base user information from the users table."""
        user_query = select(User).where(User.auth_id == user_id)
        result = await session.exec(user_query)
        return result.first()

    async def _get_user_metadata_simple(
        self, session: DBSession, user_id: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Get and process user metadata, returning simple dictionaries."""
        metadata_query = (
            select(UserMetadata).where(UserMetadata.user_auth_id == user_id).where(UserMetadata.in_used == 1)
        )
        result = await session.exec(metadata_query)
        metadata_rows = result.all()

        app_metadata_dict: dict[str, Any] = {}
        user_metadata_dict: dict[str, Any] = {}

        for metadata_row in metadata_rows:
            try:
                # Try to parse as JSON first, fallback to string
                value = json.loads(metadata_row.value) if metadata_row.value else None
            except (json.JSONDecodeError, TypeError):
                value = metadata_row.value

            if metadata_row.metadata_type == "app":
                app_metadata_dict[metadata_row.key] = value
            elif metadata_row.metadata_type == "user":
                user_metadata_dict[metadata_row.key] = value

        return app_metadata_dict, user_metadata_dict

    async def _get_user_profile(self, session: DBSession, user_id: str) -> dict[str, Any] | None:
        """Get user profile data if it exists."""
        profile_query = select(UserProfile).where(UserProfile.user_auth_id == user_id).where(UserProfile.in_used == 1)
        result = await session.exec(profile_query)
        profile_row = result.first()

        if not profile_row:
            return None

        return {
            "first_name": profile_row.first_name,
            "last_name": profile_row.last_name,
            "display_name": profile_row.display_name,
            "avatar_url": profile_row.avatar_url,
            "bio": profile_row.bio,
            "location": profile_row.location,
            "website": profile_row.website,
            "created_at": profile_row.created_at,
            "updated_at": profile_row.updated_at,
        }

    async def set_user_info(self, user_profile: UserProfileData, session: DBSession | None = None) -> bool:
        """
        Store user profile information to database.

        Args:
            user_profile: UserProfileData object containing user data
            session: Optional database session to use (for background tasks)

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If user_profile is invalid
            DBError: If database operation fails

        Example:
            >>> user_profile = UserProfileData(id="user123", email="test@example.com", ...)
            >>> success = await repo.set_user_info(user_profile)
            >>> print(success)  # True
        """
        if not user_profile:
            raise ValueError("User profile cannot be None")
        if not user_profile.id or not user_profile.id.strip():
            raise ValueError("User profile must have a valid ID")

        try:
            if session is not None:
                # Use provided session (for background tasks)
                return await self._set_user_info_impl(session, user_profile)
            # Create new transaction (normal operation)
            async with self.transaction() as db_session:
                return await self._set_user_info_impl(db_session, user_profile)
        except Exception as e:
            logger.error(f"Failed to set user info: {e}", extra={"user_id": user_profile.id})
            raise DBError(f"Failed to set user info for user {user_profile.id}: {e}") from e

    async def _set_user_info_impl(self, session: DBSession, user_profile: UserProfileData) -> bool:
        """
        Internal implementation for storing user profile information.

        Handles creating or updating user base data and metadata.

        Args:
            session: Database session
            user_profile: UserProfileData object containing user data

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create or update base user information
            await self._create_or_update_base_user_from_profile(session, user_profile)

            # Handle app metadata
            if user_profile.app_metadata:
                await self.create_or_update_user_metadata(session, user_profile.id, "app", user_profile.app_metadata)

            # Handle user metadata
            if user_profile.user_metadata:
                await self.create_or_update_user_metadata(session, user_profile.id, "user", user_profile.user_metadata)

            # Ensure user has at least one role - add default role if none exist
            await self._ensure_user_has_role(session, user_profile.id)

            await session.flush()
            logger.info(f"Successfully stored user profile for user_id: {user_profile.id}")
            return True

        except Exception as e:
            logger.error(f"Error storing user profile for user_id {user_profile.id}: {e}")
            raise

    async def _create_or_update_base_user_from_profile(self, session: DBSession, user_profile: UserProfileData) -> None:
        """Create or update base user information from UserProfileData."""
        user_query = select(User).where(User.auth_id == user_profile.id)
        result = await session.exec(user_query)
        existing_user = result.first()

        if existing_user:
            # Update existing user
            existing_user.aud = user_profile.aud or ""
            existing_user.role = user_profile.role or ""
            existing_user.email = user_profile.email or ""
            existing_user.email_confirmed_at = user_profile.email_confirmed_at
            existing_user.phone = user_profile.phone
            existing_user.confirmed_at = getattr(user_profile, "confirmed_at", None)
            existing_user.last_sign_in_at = user_profile.last_sign_in_at
            existing_user.is_anonymous = getattr(user_profile, "is_anonymous", False)
            existing_user.auth_created_at = user_profile.created_at
            existing_user.auth_updated_at = user_profile.updated_at
        else:
            # Create new user
            new_user = User(
                auth_id=user_profile.id,
                aud=user_profile.aud or "",
                role=user_profile.role or "",
                email=user_profile.email or "",
                email_confirmed_at=user_profile.email_confirmed_at,
                phone=user_profile.phone,
                confirmed_at=getattr(user_profile, "confirmed_at", None),
                last_sign_in_at=user_profile.last_sign_in_at,
                is_anonymous=getattr(user_profile, "is_anonymous", False),
                auth_created_at=user_profile.created_at,
                auth_updated_at=user_profile.updated_at,
            )
            session.add(new_user)

    async def _ensure_user_has_role(self, session: DBSession, user_id: str) -> None:
        """
        Ensure user has at least one role, add default role if none exist.

        Args:
            session: Database session
            user_id: User's authentication ID
        """
        try:
            # Check if user has any active roles
            roles_query = select(UserRole).where(UserRole.user_auth_id == user_id).where(UserRole.in_used == 1)

            roles_result = await session.exec(roles_query)
            existing_roles = roles_result.all()

            # If user has no roles, add default role
            if not existing_roles:
                default_role = UserRole(
                    user_auth_id=user_id,
                    role=self.DEFAULT_ROLE,
                    in_used=1,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                session.add(default_role)
                logger.info(f"Added default role for user {user_id} (no existing roles found)")
            else:
                logger.debug(f"User {user_id} already has {len(existing_roles)} role(s)")
        except Exception as e:
            logger.error(f"Error ensuring user has role for user_id {user_id}: {e}")
            raise

    async def get_roles(self, user_id: str) -> list[str]:
        """
        Get all roles assigned to a user.

        Args:
            user_id: User's authentication ID

        Returns:
            List of role strings assigned to the user

        Raises:
            ValueError: If user_id is empty
            DBError: If database query fails

        Example:
            >>> repo = AuthRepository()
            >>> roles = await repo.get_roles("user123")
            >>> print(roles)  # ['admin', 'user']
        """
        if not user_id or not user_id.strip():
            raise ValueError("User ID cannot be empty")

        try:
            async with self.session(readonly=True) as session:
                query = select(UserRole.role).where(UserRole.user_auth_id == user_id, UserRole.in_used == 1)
                result = await session.exec(query)
                roles = result.all()

                return list(roles) if roles else []
        except Exception as e:
            logger.error(f"Failed to get roles for user {user_id}: {e}")
            raise DBError(f"Failed to get roles for user {user_id}: {e}") from e

    async def set_roles(self, user_id: str, roles: list[str], disable_others: bool = True) -> bool:
        """
        Set roles for a user with enhanced logic for managing existing roles.

        Args:
            user_id: User's authentication ID
            roles: List of role strings to assign to the user
            disable_others: If True, disable roles not in current roles list; if False, keep existing roles

        Returns:
            True if successful

        Raises:
            ValueError: If user_id is empty or roles is None
            DBError: If database operation fails

        Logic:
            - If disable_others=True: Disable existing roles not in the current roles list
            - For roles in the list: Reactivate existing disabled roles or insert new ones
            - Avoids creating duplicate role records

        Example:
            >>> repo = AuthRepository()
            >>> success = await repo.set_roles("user123", ["admin", "user"], disable_others=True)
            >>> print(success)  # True
        """
        if not user_id or not user_id.strip():
            logger.error("User ID cannot be empty")
            return False

        try:
            async with self.transaction() as session:
                # Step 1: If disable_others=True, disable roles not in current roles list
                if disable_others:
                    # Get all active roles for the user
                    all_user_roles_query = (
                        select(UserRole).where(UserRole.user_auth_id == user_id).where(UserRole.in_used == 1)
                    )

                    all_user_roles_result = await session.exec(all_user_roles_query)
                    all_user_roles = all_user_roles_result.all()

                    # Find roles to disable (not in the current roles list)
                    roles_set = set(roles)
                    for role_record in all_user_roles:
                        if role_record.role not in roles_set:
                            role_record.in_used = 0
                            role_record.updated_at = datetime.now()
                            session.add(role_record)

                # Step 2: For each role in the roles list, reactivate or insert
                for role in roles:
                    # Try to reactivate existing disabled role using SQLModel
                    existing_disabled_role_query = (
                        select(UserRole)
                        .where(UserRole.user_auth_id == user_id)
                        .where(UserRole.role == role)
                        .where(UserRole.in_used == 0)
                    )

                    existing_disabled_result = await session.exec(existing_disabled_role_query)
                    existing_disabled_role = existing_disabled_result.first()

                    if existing_disabled_role:
                        # Reactivate the existing disabled role
                        existing_disabled_role.in_used = 1
                        existing_disabled_role.updated_at = datetime.now()
                        session.add(existing_disabled_role)
                    else:
                        # Check if role already exists and is active
                        check_stmt = (
                            select(UserRole).where(UserRole.user_auth_id == user_id).where(UserRole.role == role)
                        )
                        check_result = await session.exec(check_stmt)
                        existing_role = check_result.first()

                        # Only insert if role doesn't exist at all
                        if not existing_role:
                            new_role = UserRole(
                                user_auth_id=user_id,
                                role=role,
                                in_used=1,
                                created_at=datetime.now(),
                                updated_at=datetime.now(),
                            )
                            session.add(new_role)

                await session.flush()
                logger.info(f"Successfully set roles for user {user_id}: {roles} (disable_others={disable_others})")
                return True
        except Exception as e:
            logger.error(f"Failed to set roles for user {user_id}: {e}")
            raise DBError(f"Failed to set roles for user {user_id}: {e}") from e

    async def log_event(
        self,
        event_type: str,
        event_name: str,
        event_source: str,
        user_auth_id: str | None = None,
        trace_id: str | None = None,
        session_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        client_info: str | None = None,
        referrer: str | None = None,
        country_code: str | None = None,
        city: str | None = None,
        timezone: str | None = None,
        event_payload: dict[str, Any] | None = None,
        extra_metadata: dict[str, Any] | None = None,
        session: DBSession | None = None,
    ) -> bool:
        """
        Log a user action/event to the AUTH_USER_ACTION table.

        Args:
            event_type: Event category (auth, navigation, api_call, user_action, system)
            event_name: Specific event name (login, logout, page_view, button_click, etc.)
            event_source: Event source (supabase, frontend, api, system, mobile_app)
            user_auth_id: User auth ID (optional for anonymous events)
            trace_id: Trace ID for correlating related events
            session_id: Session ID for grouping user actions
            ip_address: Client IP address
            user_agent: Browser/client user agent string
            client_info: Additional client information
            referrer: HTTP referrer or previous page
            country_code: ISO country code derived from IP
            city: City derived from IP geolocation
            timezone: User's timezone
            event_payload: Event-specific data as dictionary (will be stored as JSON)
            extra_metadata: Additional system metadata as dictionary (will be stored as JSON)
            session: Optional database session to use

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If required parameters are invalid
            DBError: If database operation fails

        Example:
            >>> repo = AuthRepository()
            >>> success = await repo.log_event(
            ...     event_type="auth",
            ...     event_name="login",
            ...     event_source="supabase",
            ...     user_auth_id="user123",
            ...     event_payload={"provider": "google"}
            ... )
            >>> print(success)  # True
        """
        # Validate required parameters
        if not event_type or not event_type.strip():
            raise ValueError("Event type cannot be empty")
        if not event_name or not event_name.strip():
            raise ValueError("Event name cannot be empty")
        if not event_source or not event_source.strip():
            raise ValueError("Event source cannot be empty")

        try:
            if session is not None:
                # Use provided session (for background tasks or transactions)
                return await self._log_event_impl(
                    session,
                    event_type,
                    event_name,
                    event_source,
                    user_auth_id,
                    trace_id,
                    session_id,
                    ip_address,
                    user_agent,
                    client_info,
                    referrer,
                    country_code,
                    city,
                    timezone,
                    event_payload,
                    extra_metadata,
                )
            # Create new transaction (normal operation)
            async with self.transaction() as db_session:
                return await self._log_event_impl(
                    db_session,
                    event_type,
                    event_name,
                    event_source,
                    user_auth_id,
                    trace_id,
                    session_id,
                    ip_address,
                    user_agent,
                    client_info,
                    referrer,
                    country_code,
                    city,
                    timezone,
                    event_payload,
                    extra_metadata,
                )
        except Exception as e:
            logger.error(
                f"Failed to log event: {e}",
                extra={
                    "event_type": event_type,
                    "event_name": event_name,
                    "event_source": event_source,
                    "user_auth_id": user_auth_id,
                    "trace_id": trace_id,
                },
            )
            raise DBError(f"Failed to log event {event_type}/{event_name}: {e}") from e

    async def _log_event_impl(
        self,
        session: DBSession,
        event_type: str,
        event_name: str,
        event_source: str,
        user_auth_id: str | None,
        trace_id: str | None,
        session_id: str | None,
        ip_address: str | None,
        user_agent: str | None,
        client_info: str | None,
        referrer: str | None,
        country_code: str | None,
        city: str | None,
        timezone: str | None,
        event_payload: dict[str, Any] | None,
        extra_metadata: dict[str, Any] | None,
    ) -> bool:
        """
        Internal implementation for logging user actions.

        Args:
            session: Database session
            (other parameters same as log_event)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create new UserAction record
            user_action = UserAction(
                user_auth_id=user_auth_id,
                trace_id=trace_id,
                session_id=session_id,
                event_type=event_type,
                event_name=event_name,
                event_source=event_source,
                ip_address=ip_address,
                user_agent=user_agent,
                client_info=client_info,
                referrer=referrer,
                country_code=country_code,
                city=city,
                timezone=timezone,
                event_payload=json.dumps(event_payload) if event_payload else None,
                extra_metadata=json.dumps(extra_metadata) if extra_metadata else None,
                is_processed=False,
                processing_status="pending",
            )

            session.add(user_action)
            await session.flush()

            logger.info(
                f"Successfully logged event: {event_type}/{event_name} from {event_source}",
                extra={
                    "event_type": event_type,
                    "event_name": event_name,
                    "event_source": event_source,
                    "user_auth_id": user_auth_id,
                    "trace_id": trace_id,
                    "session_id": session_id,
                },
            )
            return True

        except Exception as e:
            logger.error(
                f"Error logging event {event_type}/{event_name}: {e}",
                extra={
                    "event_type": event_type,
                    "event_name": event_name,
                    "user_auth_id": user_auth_id,
                },
            )
            raise
