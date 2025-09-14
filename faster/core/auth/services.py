from datetime import datetime, timedelta
from typing import Any

from ..database import DBSession, get_transaction
from ..exceptions import DBError
from ..logger import get_logger
from ..redisex import (
    MapCategory,
    blacklist_add,
    get_user_profile,
    set_user_profile,
    sysmap_get,
    user2role_get,
    user2role_set,
)
from .auth_proxy import AuthProxy
from .models import UserProfileData
from .repositories import AuthRepository
from .schemas import User

logger = get_logger(__name__)


class AuthService:
    def __init__(
        self,
        jwt_secret: str,
        algorithms: list[str] | None = None,
        expiry_minutes: int = 60,
        supabase_url: str = "",
        supabase_anon_key: str = "",
        supabase_service_key: str = "",
        supabase_jwks_url: str = "",
        # supabase_client_id: str = "",
        supabase_audience: str = "",
        auto_refresh_jwks: bool = True,
    ):
        self._jwt_secret = jwt_secret
        self._algorithms = algorithms.split(",") if isinstance(algorithms, str) else (algorithms or ["HS2G"])
        self._expiry_minutes = expiry_minutes

        self._supabase_url = supabase_url
        self._supabase_anon_key = supabase_anon_key
        self._supabase_service_key = supabase_service_key
        self._supabase_jwks_url = supabase_jwks_url
        # self._supabase_client_id = supabase_client_id
        self._supabase_audience = supabase_audience
        self._auto_refresh_jwks = auto_refresh_jwks

        self._auth_client = AuthProxy(
            supabase_url=self._supabase_url,
            supabase_anon_key=self._supabase_anon_key,
            supabase_service_key=self._supabase_service_key,
            supabase_jwks_url=self._supabase_jwks_url,
            # supabase_client_id=self._supabase_client_id,
            supabase_audience=self._supabase_audience,
            cache_ttl=self._expiry_minutes * 60,
            auto_refresh_jwks=self._auto_refresh_jwks,
        )

        self._repository = AuthRepository()
        self._tag_role_cached: dict[str, list[str]] | None = None

    async def process_user_login(self, token: str | None, user_profile: UserProfileData) -> User:
        """
        Process user login by:
        1. Validating JWT token (handled in router/middleware)
        2. Saving/updating user profile in database
        3. Returning database user record
        """
        logger.info(f"Processing login for user: {user_profile.id}")

        # Save user profile to database
        try:
            user = await self._save_user_profile_to_database(user_profile)
            logger.info(f"Saved user profile to database: {user.auth_id}")
            return user
        except DBError as e:
            logger.error(f"Failed to save user profile to database: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving user profile to database: {e}")
            raise

    async def process_user_logout(self, token: str | None, user_profile: UserProfileData) -> None:
        """
        Process user logout operations.
        """
        user_id = user_profile.id
        try:
            # Process any logout-specific business logic here
            # (e.g., update last logout time, cleanup sessions, etc.)
            logger.info(f"Processing logout for user: {user_id}")

            # Additional logout processing can be added here
            # such as clearing user sessions, updating logout timestamps, etc.

        except Exception as e:
            logger.error(f"Failed to process logout for user {user_id}: {e}")
            raise

    async def get_roles_by_tags(self, tags: list[str]) -> set[str]:
        """
        Return set of roles for a given list of tags.
        Uses lazy initialization to cache all tag-role mappings.
        """
        if not tags:
            return set()

        # Lazy initialization: load all tag roles if not cached
        if self._tag_role_cached is None:
            all_tag_data = await sysmap_get(str(MapCategory.TAG_ROLE))
            self._tag_role_cached = all_tag_data if all_tag_data else {}

        required: set[str] = set()
        for t in tags:
            if t in self._tag_role_cached:
                roles = self._tag_role_cached[t]
                # roles is now already a list[str] from the new sysmap_get implementation
                if isinstance(roles, list):
                    r: list[str] = [str(role) for role in roles]
                else:
                    # Fallback for backward compatibility
                    r = [str(roles)]
                logger.debug(f"[RBAC] - tag: {t}, roles: {r}")
                required |= set(r)
            else:
                logger.debug(f"[RBAC] - tag: {t}, roles: []")
        return required

    def clear_tag_role_cache(self) -> None:
        """
        Clear the cached tag-role mappings.
        Useful for testing or when tag-role mappings need to be refreshed.
        """
        self._tag_role_cached = None

    def is_tag_role_cache_initialized(self) -> bool:
        """
        Check if the tag-role cache has been initialized.
        Useful for testing purposes.
        """
        return self._tag_role_cached is not None

    async def check_access(self, user_id: str, tags: list[str]) -> bool:
        """Check if user has access to a given list of tags."""
        user_roles = set(await self.get_roles(user_id))
        required_roles = await self.get_roles_by_tags(tags)

        # If endpoint has required roles, ensure intersection exists
        if required_roles:
            if user_roles.isdisjoint(required_roles):
                logger.info(f"[RBAC] - denied access(0) : {user_id} / {user_roles} for {tags} / {required_roles}")
                return False
            return True

        logger.info(f"[RBAC] - denied access(1) : {user_id} / {user_roles} for {tags} / {required_roles}")
        return False  # no required roles → deny access

    async def _save_user_profile_to_database(self, user_profile: UserProfileData) -> User:
        """Save complete user profile to database."""
        async with await get_transaction() as session:
            # Create or update user
            user_data = {
                "id": user_profile.id,
                "aud": user_profile.aud,
                "role": user_profile.role,
                "email": user_profile.email,
                "email_confirmed_at": user_profile.email_confirmed_at,
                "phone": user_profile.phone,
                "confirmed_at": user_profile.confirmed_at,
                "last_sign_in_at": user_profile.last_sign_in_at,
                "is_anonymous": user_profile.is_anonymous,
                "created_at": user_profile.created_at,
                "updated_at": user_profile.updated_at,
            }
            user = await self._repository.create_or_update_user(session, user_data)

            # Save metadata
            if user_profile.app_metadata:
                await self._repository.create_or_update_user_metadata(
                    session, user_profile.id, "app", user_profile.app_metadata
                )
            if user_profile.user_metadata:
                await self._repository.create_or_update_user_metadata(
                    session, user_profile.id, "user", user_profile.user_metadata
                )

            # Identities are now handled as part of simplified UserProfileData model

            return user

    async def _save_user_profile_to_database_with_session(
        self, session: DBSession, user_profile: UserProfileData
    ) -> User:
        """Save complete user profile to database using provided session."""
        # Create or update user
        user_data = {
            "id": user_profile.id,
            "aud": user_profile.aud,
            "role": user_profile.role,
            "email": user_profile.email,
            "email_confirmed_at": user_profile.email_confirmed_at,
            "phone": user_profile.phone,
            "confirmed_at": user_profile.confirmed_at,
            "last_sign_in_at": user_profile.last_sign_in_at,
            "is_anonymous": user_profile.is_anonymous,
            "created_at": user_profile.created_at,
            "updated_at": user_profile.updated_at,
        }
        user = await self._repository.create_or_update_user(session, user_data)

        # Save metadata
        if user_profile.app_metadata:
            await self._repository.create_or_update_user_metadata(
                session, user_profile.id, "app", user_profile.app_metadata
            )
        if user_profile.user_metadata:
            await self._repository.create_or_update_user_metadata(
                session, user_profile.id, "user", user_profile.user_metadata
            )

        # Identities are now handled as part of simplified UserProfileData model

        return user

    ###########################################################################
    # Proxy to enable external can call some methods defined in _auth_client
    ###########################################################################
    async def get_user_id_from_token(self, token: str) -> str | None:
        """Get user ID from JWT token."""
        return await self._auth_client.get_user_id_from_token(token)

    async def get_user_by_id(  # noqa: C901, PLR0912
        self, user_id: str, from_cache: bool = True, session: DBSession | None = None
    ) -> UserProfileData | None:
        """
        Get user profile data by user ID with 3-tier caching hierarchy:
        1. Try Redis cache first
        2. Try local database second
        3. Try Supabase Auth as fallback

        Args:
            user_id: User's authentication ID
            from_cache: Whether to check cache first
            session: Optional database session to use (for background tasks)
        """
        if not user_id or not user_id.strip():
            logger.error("User ID cannot be empty")
            return None

        # Step 1: Try to load from Redis cache
        if from_cache:
            try:
                cached_profile_json = await get_user_profile(user_id)
                if cached_profile_json:
                    logger.debug(f"User profile retrieved from Redis cache for user ID: {user_id}")
                    return UserProfileData.model_validate_json(cached_profile_json)
            except Exception as e:
                logger.warning(f"Failed to retrieve user profile from Redis cache: {e}")

        # Step 2: Try to load from local database
        try:
            db_profile = await self._repository.get_user_info(user_id, session)
            if db_profile:
                logger.debug(f"User profile retrieved from database for user ID: {user_id}")

                # Update Redis cache with database data
                if from_cache:
                    try:
                        profile_json = db_profile.model_dump_json()
                        cache_success = await set_user_profile(user_id, profile_json, self._expiry_minutes * 60)
                        if cache_success:
                            logger.debug(f"Updated Redis cache with database data for user ID: {user_id}")
                        else:
                            logger.warning(f"Failed to update Redis cache for user ID: {user_id}")
                    except Exception as e:
                        logger.warning(f"Error updating Redis cache from database: {e}")

                return db_profile
        except DBError as e:
            logger.warning(f"Failed to retrieve user profile from database: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error retrieving user profile from database: {e}")

        # Step 3: Fallback to Supabase Auth
        try:
            supabase_profile = await self._auth_client.get_user_by_id(user_id)
            if supabase_profile:
                logger.info(f"User profile retrieved from Supabase Auth for user ID: {user_id}")

                # Update local database with Supabase data
                try:
                    db_success = await self._repository.set_user_info(supabase_profile, session)
                    if db_success:
                        logger.debug(f"Updated database with Supabase data for user ID: {user_id}")
                    else:
                        logger.warning(f"Failed to update database for user ID: {user_id}")
                except DBError as e:
                    logger.warning(f"Error updating database from Supabase: {e}")
                except Exception as e:
                    logger.warning(f"Unexpected error updating database from Supabase: {e}")

                # Update Redis cache with Supabase data
                if from_cache:
                    try:
                        profile_json = supabase_profile.model_dump_json()
                        cache_success = await set_user_profile(user_id, profile_json, self._expiry_minutes * 60)
                        if cache_success:
                            logger.debug(f"Updated Redis cache with Supabase data for user ID: {user_id}")
                        else:
                            logger.warning(f"Failed to update Redis cache for user ID: {user_id}")
                    except Exception as e:
                        logger.warning(f"Error updating Redis cache from Supabase: {e}")

                return supabase_profile
        except Exception as e:
            logger.error(f"Failed to retrieve user profile from Supabase Auth: {e}")

        logger.error(f"User profile not found in any data source for user ID: {user_id}")
        return None

    async def get_user_by_token(self, token: str) -> UserProfileData | None:
        """Authenticate JWT token and return user profile data."""
        return await self._auth_client.get_user_by_token(token)

    ###########################################################################
    # Proxy to enable external can call some methods defined in _repository
    ###########################################################################
    async def check_user_onboarding_complete(self, user_id: str) -> bool:
        """
        Check if a user has completed onboarding by checking if they have a profile.
        """
        return await self._repository.check_user_profile_exists(user_id)

    async def get_user_by_auth_id(self, auth_id: str) -> User | None:
        """Get user from database by Supabase auth ID."""
        async with await get_transaction(readonly=True) as session:
            return await self._repository.get_user_by_auth_id(session, auth_id)

    async def get_roles(self, user_id: str, from_cache: bool = True) -> list[str]:
        """
        Get user roles from cache or database.

        Args:
            user_id: User's authentication ID
            from_cache: Whether to check cache first (default: True)

        Returns:
            List of role strings assigned to the user
        """
        # Try to get from cache first if requested
        if from_cache:
            cached_roles = await user2role_get(user_id)
            if cached_roles:
                # logger.debug(f"Retrieved roles from cache for user {user_id}: {cached_roles}")
                return cached_roles

        # Get from database if cache miss or cache disabled
        try:
            db_roles = await self._repository.get_roles(user_id)
            # logger.debug(f"Retrieved roles from database for user {user_id}: {db_roles}")

            # Update cache with database results for future requests
            if from_cache and db_roles:
                _ = await user2role_set(user_id, db_roles)
                # logger.debug(f"Updated cache with database roles for user {user_id}")

            return db_roles
        except DBError as e:
            logger.error(f"Failed to get roles for user {user_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting roles for user {user_id}: {e}")
        return []

    async def set_roles(self, user_id: str, roles: list[str], to_cache: bool = True) -> bool:
        """
        Set user roles in database and optionally update cache.

        Args:
            user_id: User's authentication ID
            roles: List of role strings to assign to the user
            to_cache: Whether to update cache after database update (default: True)

        Returns:
            True if successful, False otherwise
        """
        if not user_id or not user_id.strip() or len(roles) <= 0:
            logger.error("Cannot set roles: user_id is empty")
            return False

        try:
            # Set roles in database
            db_success = await self._repository.set_roles(user_id, roles)
            if not db_success:
                logger.error(f"Failed to set roles in database for user {user_id}")
                return False

            # Update cache if requested
            if to_cache:
                cache_success = await user2role_set(user_id, roles)
                if not cache_success:
                    logger.warning(f"Failed to update cache for user {user_id}")

            return True
        except DBError as e:
            logger.error(f"Failed to set roles for user {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error setting roles for user {user_id}: {e}")
            return False

    async def should_update_user_in_db(self, user: UserProfileData) -> bool:
        """
        Check if user information should be updated in database.
        Returns True for new users or users not updated within 24 hours.
        """
        try:
            # Check if user exists in database and get last update time
            # Use a fresh session to avoid session binding issues in background tasks
            async with await get_transaction() as session:
                db_user = await self._repository.get_user_by_auth_id(session, user.id)

                if not db_user:
                    # New user - needs to be stored
                    return True

                # Check if user was last updated more than 24 hours ago
                if db_user.updated_at:
                    time_since_update = datetime.now() - db_user.updated_at
                    return time_since_update > timedelta(hours=24)

                # If no updated_at timestamp, consider it needs update
                return True

        except DBError as e:
            logger.warning(f"Error checking user update status for {user.id}: {e}")
            # If we can't determine, err on the side of updating
            return True
        except Exception as e:
            logger.warning(f"Unexpected error checking user update status for {user.id}: {e}")
            # If we can't determine, err on the side of updating
            return True

    async def background_update_user_info(self, token: str | None, user_id: str) -> None:
        """
        Background task to update user information in database.
        Fetches fresh user data and updates the database.
        Uses a single transaction to avoid session binding issues.
        """
        try:
            logger.info(f"Updating user info in background for {user_id}")

            # Use a single transaction for all database operations to avoid session binding issues
            async with await get_transaction() as session:
                # Fetch fresh user data from external source (bypass cache for latest data)
                fresh_user_data = await self.get_user_by_id(user_id, from_cache=False, session=session)
                if not fresh_user_data:
                    logger.warning(f"Could not fetch fresh user data for {user_id}")
                    return

                # Update user info in database with fresh data using the same session
                _ = await self._save_user_profile_to_database_with_session(session, fresh_user_data)

            logger.info(f"Background user info update completed for {user_id}")
        except DBError as e:
            logger.error(f"Database error in background user info update for {user_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in background user info update for {user_id}: {e}")

    async def background_process_logout(self, token: str | None, user: UserProfileData) -> None:
        """
        Background task to process user logout operations.
        Handles both token blacklisting and business logic processing.
        """
        try:
            logger.info(f"Processing logout in background for {user.id}")

            # Add token to blacklist
            if token:
                blacklist_success = await blacklist_add(token)
                if blacklist_success:
                    logger.debug(f"Added token to blacklist for user {user.id}")
                else:
                    logger.warning(f"Failed to add token to blacklist for user {user.id}")

            # Process additional logout business logic
            await self.process_user_logout(token, user)
            logger.info(f"Background logout processing completed for {user.id}")

        except Exception as e:
            logger.error(f"Unexpected error in background logout processing for {user.id}: {e}")

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
        """
        try:
            return await self._repository.log_event(
                event_type=event_type,
                event_name=event_name,
                event_source=event_source,
                user_auth_id=user_auth_id,
                trace_id=trace_id,
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent,
                client_info=client_info,
                referrer=referrer,
                country_code=country_code,
                city=city,
                timezone=timezone,
                event_payload=event_payload,
                extra_metadata=extra_metadata,
                session=session,
            )
        except Exception as e:
            logger.error(f"AuthService.log_event failed: {e}")
            # Never re-raise exceptions to avoid disrupting the main application flow
            # Event logging is for tracking/analytics and should not interfere with core functionality
            return False
