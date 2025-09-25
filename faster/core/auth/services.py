from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request

from ..config import Settings
from ..database import DBSession, get_transaction
from ..exceptions import DBError
from ..logger import get_logger
from ..plugins import BasePlugin
from ..redisex import (
    blacklist_add,
    get_user_profile,
    set_user_profile,
    user2role_get,
    user2role_set,
)
from ..repositories import AppRepository
from .auth_proxy import AuthProxy
from .models import AuthServiceConfig, RouterItem, UserProfileData
from .repositories import AuthRepository
from .router_info import RouterInfo
from .schemas import User
from .utilities import generate_trace_id, mask_sensitive_data

logger = get_logger(__name__)


class AuthService(BasePlugin):
    def __init__(self) -> None:
        # Lazy initialization - actual setup happens in setup() method
        self._auth_client: AuthProxy | None = None
        self._repository: AuthRepository | None = None

        # Router information management
        self._router_info = RouterInfo()

        # Configuration storage - only cache needed settings
        self._config: AuthServiceConfig | None = None
        self._is_setup: bool = False

    # -----------------------------
    # Plugin interface implementation
    # -----------------------------
    async def setup(self, settings: Settings) -> bool:
        """Initialize the AuthService with configuration."""
        try:
            # Extract only the needed settings to save memory and prevent abuse
            self._config = AuthServiceConfig(
                auth_enabled=settings.auth_enabled,
                supabase_url=settings.supabase_url,
                supabase_anon_key=settings.supabase_anon_key,
                supabase_service_role_key=settings.supabase_service_role_key,
                supabase_jwks_url=settings.supabase_jwks_url,
                supabase_audience=settings.supabase_audience,
                jwks_cache_ttl_seconds=settings.jwks_cache_ttl_seconds,
                auto_refresh_jwks=settings.auto_refresh_jwks,
                user_cache_ttl_seconds=settings.user_cache_ttl_seconds,
                is_debug=settings.is_debug,
            )

            if not self._config["auth_enabled"]:
                logger.info("Auth is disabled, AuthService will be available but not active")
                self._is_setup = True
                return True

            # Initialize auth proxy
            jwks_url = self._config["supabase_jwks_url"]
            if not jwks_url:
                jwks_url = (self._config["supabase_url"] or "") + "/auth/v1/.well-known/jwks.json"

            self._auth_client = AuthProxy(
                supabase_url=self._config["supabase_url"] or "",
                supabase_anon_key=self._config["supabase_anon_key"] or "",
                supabase_service_role_key=self._config["supabase_service_role_key"] or "",
                supabase_jwks_url=jwks_url,
                supabase_audience=self._config["supabase_audience"] or "",
                cache_ttl=self._config["jwks_cache_ttl_seconds"],
                auto_refresh_jwks=self._config["auto_refresh_jwks"],
            )

            # Initialize repository
            self._repository = AuthRepository()

            self._is_setup = True
            logger.info("AuthService setup completed successfully")

            # Trigger health check to load initial data
            _ = await self.check_health()
            return True

        except Exception as e:
            logger.error(f"AuthService setup failed: {e}")
            return False

    def set_test_config(self, config: AuthServiceConfig) -> None:
        """Set configuration for testing purposes. Only use in tests."""
        self._config = config
        self._is_setup = True

    async def teardown(self) -> bool:
        """Clean up AuthService resources."""
        try:
            # Clear router info caches
            self._router_info.reset_cache()

            # Clear auth client cache if exists
            if self._auth_client:
                self._auth_client.clear_jwks_cache()

            self._is_setup = False
            logger.info("AuthService teardown completed successfully")
            return True

        except Exception as e:
            logger.error(f"AuthService teardown failed: {e}")
            return False

    async def check_health(self) -> dict[str, Any]:
        """Check AuthService health and refresh cached data."""
        if not self._is_setup:
            return {"is_ready": False, "auth_enabled": False}

        # Get current cache sizes from router info
        cache_info = self._router_info.get_cache_info()
        health_status = {
            "is_ready": self._is_setup,
            "auth_enabled": self._config["auth_enabled"] if self._config else False,
            "tag_role_cache_size": cache_info["tag_role_cache_size"],
            "route_cache_size": cache_info["route_cache_size"],
        }

        try:
            # Get JWKS cache info if auth client exists
            if self._auth_client:
                jwks_info = self._auth_client.get_jwks_cache_info()
                health_status["jwks_cache"] = jwks_info  # type: ignore[assignment]

        except Exception as e:
            logger.error(f"Error during AuthService health check: {e}")
            health_status["is_ready"] = False
            health_status["error"] = str(e)  # type: ignore[assignment]

        return health_status

    ###########################################################################
    # Proxy to enable external can call some methods defined in _router_info
    ###########################################################################
    def get_router_info(self) -> "RouterInfo":  ## so far, only used for testing
        """
        Get the RouterInfo instance for advanced usage.

        Returns:
            RouterInfo instance used by this AuthService
        """
        return self._router_info

    async def refresh_data(self, app: FastAPI, is_debug: bool = False) -> list[RouterItem]:
        """
        Refresh router data from FastAPI app and compute allowed roles for each route.
        Also creates the route finder for fast route matching.
        Delegates to RouterInfo for implementation.
        """
        router_items = await self._router_info.refresh_data(app, is_debug)
        # Create route finder as part of refresh process
        _ = self._router_info.create_route_finder(app)
        return router_items

    def find_route(self, method: str, path: str) -> RouterItem | None:
        """
        Find route information for given method and path using cached finder.
        Delegates to RouterInfo for implementation.
        """
        return self._router_info.find_route(method, path)

    def is_public_route(self, method: str, path: str) -> bool:
        """
        Check if route is public.
        Delegates to RouterInfo for implementation.
        """
        route_item = self.find_route(method, path)
        return route_item is not None and hasattr(route_item, "tags") and "public" in route_item["tags"]

    async def check_access(self, user_roles: set[str], allowed_roles: set[str]) -> bool:
        """Check if user has access to a given list of tags."""
        return await self._router_info.check_access(user_roles, allowed_roles)

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
            if not self._repository:
                logger.error("AuthService repository not initialized")
                raise DBError("Repository not available")
            user = await self._repository.create_or_update_user(session, user_data)

            # Save metadata
            if self._repository:
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
        if not self._repository:
            logger.error("AuthService repository not initialized")
            raise DBError("Repository not available")
        user = await self._repository.create_or_update_user(session, user_data)

        # Save metadata
        if self._repository:
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
        if not self._auth_client:
            logger.error("AuthService not properly initialized")
            return None
        return await self._auth_client.get_user_id_from_token(token)

    async def get_user_by_id(  # noqa: C901, PLR0912, PLR0911
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
                cached_profile = await get_user_profile(user_id)
                if cached_profile:
                    logger.debug(f"User profile retrieved from Redis cache for user ID: {user_id}")
                    return cached_profile
            except Exception as e:
                logger.warning(f"Failed to retrieve user profile from Redis cache: {e}")

        # Step 2: Try to load from local database
        try:
            if not self._repository:
                logger.error("AuthService repository not initialized")
                return None
            db_profile = await self._repository.get_user_info(user_id, session)
            if db_profile:
                logger.debug(f"User profile retrieved from database for user ID: {user_id}")

                # Update Redis cache with database data
                if from_cache:
                    _ = await self.refresh_user_cache(user_id, user_profile=db_profile)

                return db_profile
        except DBError as e:
            logger.warning(f"Failed to retrieve user profile from database: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error retrieving user profile from database: {e}")

        # Step 3: Fallback to Supabase Auth
        try:
            if not self._auth_client:
                logger.error("AuthService not properly initialized")
                return None
            supabase_profile = await self._auth_client.get_user_by_id(user_id)
            if supabase_profile:
                logger.info(f"User profile retrieved from Supabase Auth for user ID: {user_id}")

                # Update local database with Supabase data
                try:
                    if self._repository:
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
                    _ = await self.refresh_user_cache(user_id, user_profile=supabase_profile)

                return supabase_profile
        except Exception as e:
            logger.error(f"Failed to retrieve user profile from Supabase Auth: {e}")

        logger.error(f"User profile not found in any data source for user ID: {user_id}")
        return None

    async def get_user_by_token(self, token: str) -> UserProfileData | None:
        """Authenticate JWT token and return user profile data."""
        if not self._auth_client:
            logger.error("AuthService not properly initialized")
            return None
        return await self._auth_client.get_user_by_token(token)

    ###########################################################################
    # Proxy to enable external can call some methods defined in _repository
    ###########################################################################
    async def check_user_onboarding_complete(self, user_id: str) -> bool:
        """
        Check if a user has completed onboarding by checking:
        1. User metadata has onboarding_complete: true
        2. Fallback to checking if they have a profile in the database
        """
        if not self._auth_client:
            logger.error("AuthService not properly initialized")
            return False

        # First, try to get user from Supabase Auth to check metadata
        try:
            user_data = await self.get_user_by_id(user_id, from_cache=True)
            if user_data and user_data.user_metadata:
                onboarding_complete = user_data.user_metadata.get("onboarding_complete", False)
                if onboarding_complete:
                    logger.debug(f"User {user_id} has completed onboarding via metadata")
                    return True

        except Exception as e:
            logger.warning(f"Failed to check user metadata for onboarding status: {e}")

        # Fallback: check if user has a profile in the database
        if not self._repository:
            logger.error("AuthService repository not initialized")
            return False

        profile_exists = await self._repository.check_user_profile_exists(user_id)
        if profile_exists:
            logger.debug(f"User {user_id} has completed onboarding via profile existence")

        return profile_exists

    async def get_user_by_auth_id(self, auth_id: str) -> User | None:
        """Get user from database by Supabase auth ID."""
        if not self._repository:
            logger.error("AuthService repository not initialized")
            return None
        return await self._repository.get_user_by_auth_id_simple(auth_id)

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
            if not self._repository:
                logger.error("AuthService repository not initialized")
                return []
            db_roles = await self._repository.get_roles(user_id)
            # logger.debug(f"Retrieved roles from database for user {user_id}: {db_roles}")

            # Update cache with database results for future requests
            if from_cache and db_roles:
                _ = await self.refresh_user_cache(user_id, roles=db_roles)

            return db_roles
        except DBError as e:
            logger.error(f"Failed to get roles for user {user_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting roles for user {user_id}: {e}")
        return []

    async def get_all_available_roles(self) -> list[str]:
        """
        Get all available roles from system configuration.

        Returns:
            List of all available role strings from sys_dict with category 'user_role'
        """
        try:
            app_repository = AppRepository()
            sys_dict_data = await app_repository.get_sys_dict(category="user_role")

            # Extract roles from the sys_dict structure: {"user_role": {key: role_name}}
            user_role_dict = sys_dict_data.get("user_role", {})
            roles = list(user_role_dict.values())

            return sorted(roles) if roles else []
        except DBError as e:
            logger.error(f"Failed to get available roles from sys_dict: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting available roles: {e}")
        return []

    async def refresh_user_cache(
        self,
        user_id: str,
        user_profile: UserProfileData | None = None,
        roles: list[str] | None = None,
        force_refresh: bool = False,
    ) -> bool:
        """
        Refresh user cache in Redis with user profile and role information.

        Args:
            user_id: User's authentication ID
            user_profile: User profile data to cache (optional)
            roles: List of roles to cache (optional)
            force_refresh: If True, load missing data from database/external sources

        Returns:
            True if cache refresh was successful, False otherwise

        Logic:
            - If force_refresh=True and user_profile/roles is None, load from database
            - If force_refresh=False and user_profile/roles is None, skip that part
            - Always cache provided non-None values
        """
        if not user_id or not user_id.strip():
            logger.error("User ID cannot be empty for cache refresh")
            return False

        try:
            ttl = self._config["user_cache_ttl_seconds"] if self._config else 3600
            profile_success = await self._refresh_user_profile_cache(user_id, user_profile, force_refresh, ttl)
            roles_success = await self._refresh_user_roles_cache(user_id, roles, force_refresh)
            return profile_success and roles_success
        except Exception as e:
            logger.error(f"Unexpected error refreshing cache for user {user_id}: {e}")
            return False

    async def _refresh_user_profile_cache(
        self, user_id: str, user_profile: UserProfileData | None, force_refresh: bool, ttl: int
    ) -> bool:
        """Helper method to refresh user profile cache."""
        profile_to_cache = user_profile
        if profile_to_cache is None and force_refresh:
            profile_to_cache = await self.get_user_by_id(user_id, from_cache=False)

        if profile_to_cache is None:
            return True  # Nothing to cache, consider success

        try:
            cache_success = await set_user_profile(user_id, profile_to_cache, ttl)
            if cache_success:
                logger.debug(f"Refreshed user profile cache for user ID: {user_id}")
            else:
                logger.warning(f"Failed to refresh user profile cache for user ID: {user_id}")
            return cache_success
        except Exception as e:
            logger.error(f"Error refreshing user profile cache for user {user_id}: {e}")
            return False

    async def _refresh_user_roles_cache(self, user_id: str, roles: list[str] | None, force_refresh: bool) -> bool:
        """Helper method to refresh user roles cache."""
        roles_to_cache = roles
        if roles_to_cache is None and force_refresh:
            roles_to_cache = await self.get_roles(user_id, from_cache=False)

        if roles_to_cache is None:
            return True  # Nothing to cache, consider success

        try:
            cache_success = await user2role_set(user_id, roles_to_cache)
            if cache_success:
                logger.debug(f"Refreshed user roles cache for user ID: {user_id}")
            else:
                logger.warning(f"Failed to refresh user roles cache for user ID: {user_id}")
            return cache_success
        except Exception as e:
            logger.error(f"Error refreshing user roles cache for user {user_id}: {e}")
            return False

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
            if not self._repository:
                logger.error("AuthService repository not initialized")
                return False
            # Set roles in database
            db_success = await self._repository.set_roles(user_id, roles)
            if not db_success:
                logger.error(f"Failed to set roles in database for user {user_id}")
                return False

            # Update cache if requested
            if to_cache:
                _ = await self.refresh_user_cache(user_id, roles=roles)

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
        if not self._repository:
            logger.error("AuthService repository not initialized")
            return True  # Assume needs update if can't check

        return await self._repository.should_update_user_in_db(user.id)

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

    def _sanitize_event_payload(self, payload: dict[str, Any] | None) -> dict[str, Any] | None:
        """
        Sanitize event payload by removing or masking sensitive data.

        Args:
            payload: Raw event payload

        Returns:
            Sanitized payload safe for logging
        """
        if not payload:
            return payload

        sanitized = payload.copy()

        # Mask sensitive fields
        sensitive_fields = {"password", "token", "secret", "key", "auth_token", "api_key"}
        for field in sensitive_fields:
            if field in sanitized and isinstance(sanitized[field], str):
                sanitized[field] = mask_sensitive_data(sanitized[field])

        # Remove extremely large values that might cause performance issues
        for key, value in sanitized.items():
            if isinstance(value, str) and len(value) > 1000:
                sanitized[key] = value[:1000] + "...[truncated]"
            elif isinstance(value, list | dict) and len(str(value)) > 2000:
                sanitized[key] = f"{type(value).__name__} too large to log"

        return sanitized

    def _enrich_event_metadata(
        self, metadata: dict[str, Any] | None, user_auth_id: str | None, ip_address: str | None
    ) -> dict[str, Any] | None:
        """
        Enrich event metadata with additional context information.

        Args:
            metadata: Existing metadata
            user_auth_id: User authentication ID
            ip_address: Client IP address

        Returns:
            Enriched metadata dictionary
        """
        enriched = metadata.copy() if metadata else {}

        # Add timestamp if not present
        if "timestamp" not in enriched:
            enriched["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Add user context
        if user_auth_id:
            enriched["user_id"] = user_auth_id

        # Add security context
        if ip_address:
            # Store IP for analytics but mark as potentially sensitive
            enriched["client_ip"] = ip_address
            enriched["ip_logged"] = True

        # Add service version/context
        enriched["service"] = "faster_auth"
        enriched["version"] = getattr(self._config, "version", "unknown") if self._config else "unknown"

        return enriched

    async def log_event_raw(  # noqa: C901, PLR0912
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
        request: Request | None = None,
    ) -> bool:
        """
        Log a user action/event to the AUTH_USER_ACTION table with business logic validation.

        This method provides centralized event logging with:
        - Input validation and sanitization
        - Event enrichment and normalization
        - Security checks and rate limiting considerations
        - Structured error handling
        - Auto-extraction of common fields from request object

        Args:
            event_type: Type of event (e.g., 'user', 'admin', 'auth')
            event_name: Specific event name (e.g., 'login', 'profile_update')
            event_source: Source of the event (e.g., 'user_action', 'admin_action')
            user_auth_id: User authentication ID
            trace_id: Request trace ID (auto-extracted from X-Request-ID header if request provided)
            session_id: Session identifier (defaults to user_auth_id for grouping)
            ip_address: Client IP address (auto-extracted from request)
            user_agent: User agent string (auto-extracted from request headers)
            client_info: Additional client information
            referrer: HTTP referrer header (auto-extracted from request)
            country_code: Client country code
            city: Client city
            timezone: Client timezone
            event_payload: Structured event data
            extra_metadata: Additional metadata (auto-includes request method/URL if request provided)
            session: Optional database session to use
            request: FastAPI Request object for automatic field extraction
        """
        try:
            # Input validation
            if not event_type or not event_type.strip():
                logger.warning("Event logging failed: event_type is required")
                return False

            if not event_name or not event_name.strip():
                logger.warning("Event logging failed: event_name is required")
                return False

            if not event_source or not event_source.strip():
                logger.warning("Event logging failed: event_source is required")
                return False

            # Normalize and validate event_type
            valid_event_types = {"auth", "user", "admin", "password", "system"}
            if event_type not in valid_event_types:
                logger.warning(f"Event logging: unknown event_type '{event_type}', proceeding anyway")

            # Normalize and validate event_source
            valid_event_sources = {"user_action", "admin_action", "supabase", "system", "api"}
            if event_source not in valid_event_sources:
                logger.warning(f"Event logging: unknown event_source '{event_source}', proceeding anyway")

            # Auto-extract common fields from request if not provided
            if request and not trace_id:
                trace_id = request.headers.get("X-Request-ID")

            if request and not ip_address:
                ip_address = getattr(request.client, "host", None) if request.client else None

            if request and not user_agent:
                user_agent = request.headers.get("user-agent")

            if request and not referrer:
                referrer = request.headers.get("referer")  # Note: 'referer' is the actual header name

            # Use user_auth_id as session_id if not provided (groups actions by user)
            if not session_id and user_auth_id:
                session_id = user_auth_id

            # Auto-add request metadata if request provided and no extra_metadata
            if request and not extra_metadata:
                extra_metadata = {
                    "request_method": request.method,
                    "url": str(request.url),
                }

            # Sanitize and enrich event data
            sanitized_payload = self._sanitize_event_payload(event_payload)
            enriched_metadata = self._enrich_event_metadata(extra_metadata, user_auth_id, ip_address)

            # Generate trace_id if not provided
            if not trace_id:
                trace_id = generate_trace_id()

            # Set session_id to user_auth_id if not provided (for grouping)
            if not session_id and user_auth_id:
                session_id = user_auth_id

            # Security: Mask sensitive data in logs
            if ip_address:
                # Don't log full IP addresses in production logs for privacy
                logger.debug(f"Event {event_name} from IP: {mask_sensitive_data(ip_address, visible_chars=2)}")

            # Repository layer call
            if not self._repository:
                logger.error("AuthService repository not initialized")
                return False

            success = await self._repository.log_event(
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
                event_payload=sanitized_payload,
                extra_metadata=enriched_metadata,
                session=session,
            )

            if success:
                logger.debug(f"Successfully logged event: {event_type}.{event_name} from {event_source}")
            else:
                logger.warning(f"Failed to log event: {event_type}.{event_name} from {event_source}")

            return success

        except Exception as e:
            logger.error(f"Unexpected error logging event {event_name}: {e}")
            # Don't re-raise exceptions to avoid disrupting the main application flow
            return False

    # =============================================================================
    # Password Management Methods
    # =============================================================================

    async def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        """
        Change user password with current password verification.

        Args:
            user_id: User's authentication ID
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            True if password changed successfully, False otherwise
        """
        try:
            if not self._auth_client:
                logger.error("AuthService not properly initialized")
                return False

            # Use auth proxy to change password via Supabase
            result = await self._auth_client.change_password(user_id, current_password, new_password)

            if result:
                logger.info(f"Password changed successfully for user {user_id}")
                # Log the password change event
                _ = await self.log_event_raw(
                    event_type="auth",
                    event_name="password_changed",
                    event_source="user_action",
                    user_auth_id=user_id,
                    session_id=user_id,  # Use user_id as session_id for grouping
                    event_payload={"status": "success"},
                )
            else:
                logger.warning(f"Password change failed for user {user_id}")

            return result

        except Exception as e:
            logger.error(f"Error changing password for user {user_id}: {e}")
            return False

    async def initiate_password_reset(self, email: str) -> bool:
        """
        Initiate password reset process by sending reset email.

        Args:
            email: Email address to send reset link to

        Returns:
            True if reset email sent successfully, False otherwise
        """
        try:
            if not self._auth_client:
                logger.error("AuthService not properly initialized")
                return False

            # Use auth proxy to initiate password reset via Supabase
            result = await self._auth_client.initiate_password_reset(email)

            if result:
                logger.info(f"Password reset initiated for email {email}")
                # Log the password reset initiation event
                _ = await self.log_event_raw(
                    event_type="auth",
                    event_name="password_reset_initiated",
                    event_source="user_action",
                    event_payload={"email": email, "status": "success"},
                )
            else:
                logger.warning(f"Password reset initiation failed for email {email}")

            return result

        except Exception as e:
            logger.error(f"Error initiating password reset for email {email}: {e}")
            return False

    async def confirm_password_reset(self, token: str, new_password: str) -> bool:
        """
        Confirm password reset with token and set new password.

        Args:
            token: Password reset token
            new_password: New password to set

        Returns:
            True if password reset completed successfully, False otherwise
        """
        try:
            if not self._auth_client:
                logger.error("AuthService not properly initialized")
                return False

            # Use auth proxy to confirm password reset via Supabase
            result = await self._auth_client.confirm_password_reset(token, new_password)

            if result:
                logger.info("Password reset confirmed successfully")
                # Log the password reset completion event
                _ = await self.log_event_raw(
                    event_type="auth",
                    event_name="password_reset_completed",
                    event_source="user_action",
                    event_payload={"status": "success"},
                )
            else:
                logger.warning("Password reset confirmation failed")

            return result

        except Exception as e:
            logger.error(f"Error confirming password reset: {e}")
            return False

    # =============================================================================
    # Account Management Methods
    # =============================================================================

    async def deactivate(self, user_id: str, password: str) -> bool:
        """
        Deactivate user account with password verification.
        This performs a comprehensive deactivation including all associated data.

        Args:
            user_id: User's authentication ID
            password: Password for verification

        Returns:
            True if account deactivated successfully, False otherwise
        """
        try:
            if not self._repository:
                logger.error("AuthService repository not initialized")
                return False

            # Verify password before deactivation
            if not await self._verify_user_password(user_id, password):
                logger.warning(f"Password verification failed for account deactivation: {user_id}")
                return False

            # Deactivate account in database (comprehensive deactivation)
            result = await self._repository.deactivate(user_id)

            if result:
                logger.info(f"Account deactivated successfully for user {user_id}")

                # Refresh cache to remove deactivated user from cache (force_refresh=True to clear cache)
                _ = await self.refresh_user_cache(user_id, force_refresh=True)

                # Log the account deactivation event
                _ = await self.log_event_raw(
                    event_type="auth",
                    event_name="account_deactivated",
                    event_source="user_action",
                    user_auth_id=user_id,
                    session_id=user_id,  # Use user_id as session_id for grouping
                    event_payload={"status": "success"},
                )

                # Also deactivate from Supabase Auth if possible
                try:
                    if self._auth_client:
                        _ = await self._auth_client.delete_user(user_id)
                        logger.info(f"User deactivated from Supabase Auth: {user_id}")
                except Exception as e:
                    logger.warning(f"Failed to deactivate user from Supabase Auth: {e}")

            else:
                logger.warning(f"Account deactivation failed for user {user_id}")

            return result

        except Exception as e:
            logger.error(f"Error deactivating account for user {user_id}: {e}")
            return False

    # =============================================================================
    # User Administration Methods
    # =============================================================================

    async def ban_user(self, user_id: str, target_user_identifier: str, reason: str = "") -> bool:
        """
        Ban a user account.
        Supports lookup by user ID or email address.

        Args:
            user_id: User ID performing the action
            target_user_identifier: User ID or email address to ban
            reason: Reason for banning

        Returns:
            True if user banned successfully, False otherwise
        """
        try:
            if not self._repository:
                logger.error("AuthService repository not initialized")
                return False

            # Get actual user ID from identifier
            async with await get_transaction() as session:
                # Detect if identifier is email or user ID
                is_email = "@" in target_user_identifier

                if is_email:
                    user_info = await self._repository.get_user_by_email(session, target_user_identifier)
                    lookup_type = "email"
                else:
                    user_info = await self._repository.get_user_by_auth_id(session, target_user_identifier)
                    lookup_type = "user_id"

                if not user_info:
                    logger.warning(f"User not found by {lookup_type}: {target_user_identifier}")
                    return False

                actual_user_id = user_info.auth_id

            # Ban user in database
            result = await self._repository.ban_user(actual_user_id, user_id, reason)

            if result:
                logger.info(f"User {target_user_identifier} (by {lookup_type}) banned by user {user_id}")

                # Refresh cache to remove banned user from cache (force_refresh=True to clear cache)
                _ = await self.refresh_user_cache(actual_user_id, force_refresh=True)

                # Log the ban event
                _ = await self.log_event_raw(
                    event_type="admin",
                    event_name="user_banned",
                    event_source="admin_action",
                    user_auth_id=user_id,
                    session_id=user_id,  # Use user_id as session_id for grouping
                    event_payload={
                        "target_user_identifier": target_user_identifier,
                        "lookup_type": lookup_type,
                        "actual_user_id": actual_user_id,
                        "reason": reason,
                        "status": "success",
                    },
                )
            else:
                logger.warning(f"Failed to ban user {target_user_identifier} by user {user_id}")

            return result

        except Exception as e:
            logger.error(f"Error banning user {target_user_identifier} by user {user_id}: {e}")
            return False

    async def unban_user(self, user_id: str, target_user_identifier: str) -> bool:
        """
        Unban a user account.
        Supports lookup by user ID or email address.

        Args:
            user_id: User ID performing the action
            target_user_identifier: User ID or email address to unban

        Returns:
            True if user unbanned successfully, False otherwise
        """
        try:
            if not self._repository:
                logger.error("AuthService repository not initialized")
                return False

            # Get actual user ID from identifier
            async with await get_transaction() as session:
                # Detect if identifier is email or user ID
                is_email = "@" in target_user_identifier

                if is_email:
                    user_info = await self._repository.get_user_by_email(session, target_user_identifier)
                    lookup_type = "email"
                else:
                    user_info = await self._repository.get_user_by_auth_id(session, target_user_identifier)
                    lookup_type = "user_id"

                if not user_info:
                    logger.warning(f"User not found by {lookup_type}: {target_user_identifier}")
                    return False

                actual_user_id = user_info.auth_id

            # Unban user in database
            result = await self._repository.unban_user(actual_user_id, user_id)

            if result:
                logger.info(f"User {target_user_identifier} (by {lookup_type}) unbanned by user {user_id}")

                # Refresh cache to restore unbanned user to cache (force_refresh=True to reload from DB)
                _ = await self.refresh_user_cache(actual_user_id, force_refresh=True)

                # Log the unban event
                _ = await self.log_event_raw(
                    event_type="admin",
                    event_name="user_unbanned",
                    event_source="admin_action",
                    user_auth_id=user_id,
                    session_id=user_id,  # Use user_id as session_id for grouping
                    event_payload={
                        "target_user_identifier": target_user_identifier,
                        "lookup_type": lookup_type,
                        "actual_user_id": actual_user_id,
                        "status": "success",
                    },
                )
            else:
                logger.warning(f"Failed to unban user {target_user_identifier} by user {user_id}")

            return result

        except Exception as e:
            logger.error(f"Error unbanning user {target_user_identifier} by user {user_id}: {e}")
            return False

    # =============================================================================
    # Role Management Methods
    # =============================================================================

    async def get_user_roles_by_id(self, user_id: str, target_user_id: str) -> list[str] | None:
        """
        Get user roles for a target user.

        Args:
            user_id: User ID performing the action
            target_user_id: User ID to get roles for

        Returns:
            List of roles if successful, None if error
        """
        try:
            # Get roles using existing method
            roles = await self.get_roles(target_user_id, from_cache=True)

            logger.info(f"Roles for user {target_user_id} retrieved by user {user_id}")
            # Log the role view event
            _ = await self.log_event_raw(
                event_type="admin",
                event_name="user_roles_viewed",
                event_source="admin_action",
                user_auth_id=user_id,
                session_id=user_id,  # Use user_id as session_id for grouping
                event_payload={"target_user_id": target_user_id, "status": "success"},
            )

            return roles

        except Exception as e:
            logger.error(f"Error getting roles for user {target_user_id} by user {user_id}: {e}")
            return None

    async def get_user_basic_info_by_id(
        self,
        user_id: str,
        target_user_identifier: str,
    ) -> dict[str, Any] | None:
        """
        Get user basic information including ID, email, status, and roles.
        Supports lookup by user ID or email address.

        Args:
            user_id: User ID performing the action
            target_user_identifier: User ID or email address to get basic info for

        Returns:
            Dictionary with user basic info if successful, None if error
        """
        try:
            # Get user from database
            if not self._repository:
                logger.error("AuthService not properly initialized")
                return None

            async with await get_transaction() as session:
                # Detect if identifier is email or user ID
                is_email = "@" in target_user_identifier

                if is_email:
                    user_info = await self._repository.get_user_by_email(session, target_user_identifier)
                    lookup_type = "email"
                else:
                    user_info = await self._repository.get_user_by_auth_id(session, target_user_identifier)
                    lookup_type = "user_id"

                if not user_info:
                    logger.warning(f"User not found by {lookup_type}: {target_user_identifier}")
                    return None

                # Get the actual user ID for role lookup
                actual_user_id = user_info.auth_id

                # Get roles using existing method
                roles = await self.get_roles(actual_user_id, from_cache=True)

                # Determine user status by checking both user record and metadata
                status = await self._repository.determine_user_status(session, user_info, actual_user_id)

                # Build basic info response
                basic_info = {"id": actual_user_id, "email": user_info.email, "status": status, "roles": roles}

            logger.info(f"Basic info for user {target_user_identifier} (by {lookup_type}) retrieved by user {user_id}")
            return basic_info

        except Exception as e:
            logger.error(f"Error getting basic info for user {target_user_identifier} by user {user_id}: {e}")
            return None

    async def adjust_roles(
        self,
        user_id: str,
        target_user_identifier: str,
        roles: list[str],
    ) -> bool:
        """
        Adjust user roles by replacing all existing roles with the provided roles list.
        Supports lookup by user ID or email address.

        Args:
            user_id: User ID performing the action
            target_user_identifier: User ID or email address to adjust roles for
            roles: List of roles to assign to the user

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate that at least one role is provided
            if not roles or len(roles) == 0:
                logger.warning(
                    f"Attempt to adjust roles with empty roles list for user {target_user_identifier} by user {user_id}"
                )
                return False

            if not self._repository:
                logger.error("AuthService not properly initialized")
                return False

            # Get actual user ID from identifier
            user_info, lookup_type = await self._repository.get_user_by_identifier(target_user_identifier)

            if not user_info:
                logger.warning(f"User not found by {lookup_type}: {target_user_identifier}")
                return False

            actual_user_id = user_info.auth_id

            # Replace all roles with the new roles list
            result = await self._repository.adjust_roles(actual_user_id, roles, user_id)

            if result:
                # Refresh cache with new roles
                _ = await self.refresh_user_cache(actual_user_id, roles=roles)

                logger.info(
                    f"Roles adjusted for user {target_user_identifier} (by {lookup_type}) by user {user_id}, new roles: {roles}"
                )
            else:
                logger.warning(f"Failed to adjust roles for user {target_user_identifier} by user {user_id}")

            return result

        except Exception as e:
            logger.error(f"Error adjusting roles for user {target_user_identifier} by user {user_id}: {e}")
            return False

    # =============================================================================
    # Helper Methods
    # =============================================================================

    async def _determine_user_status_by_id(self, user_id: str) -> str:
        """
        Determine user status by user ID (convenience method for middleware).

        Args:
            user_id: User authentication ID

        Returns:
            Status string: "active", "banned", or "deactivated"
        """
        if not self._repository:
            logger.error("AuthService repository not initialized")
            return "deactivated"

        user_info = await self._repository.get_user_by_auth_id_simple(user_id)
        if not user_info:
            return "deactivated"

        # For status determination, we still need a session to check metadata
        async with await get_transaction() as session:
            return await self._repository.determine_user_status(session, user_info, user_id)

    async def _verify_user_password(self, user_id: str, password: str) -> bool:
        """
        Verify user password using Supabase Auth.

        Args:
            user_id: User's authentication ID
            password: Password to verify

        Returns:
            True if password is correct, False otherwise
        """
        try:
            if not self._auth_client:
                logger.error("AuthService not properly initialized")
                return False

            # Use auth proxy to verify password via Supabase
            result = await self._auth_client.verify_password(user_id, password)
            return result

        except Exception as e:
            logger.error(f"Error verifying password for user {user_id}: {e}")
            return False
