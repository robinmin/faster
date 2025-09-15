from collections.abc import Callable
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, TypedDict

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.routing import Match

from ..config import Settings
from ..database import DBSession, get_transaction
from ..exceptions import DBError
from ..logger import get_logger
from ..plugins import BasePlugin
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


class AuthServiceConfig(TypedDict):
    """Configuration for AuthService containing only the needed settings."""

    auth_enabled: bool
    supabase_url: str | None
    supabase_anon_key: str | None
    supabase_service_key: str | None
    supabase_jwks_url: str | None
    supabase_audience: str | None
    jwks_cache_ttl_seconds: int
    auto_refresh_jwks: bool
    user_cache_ttl_seconds: int
    is_debug: bool


logger = get_logger(__name__)


class AuthService(BasePlugin):
    def __init__(self) -> None:
        # Lazy initialization - actual setup happens in setup() method
        self._auth_client: AuthProxy | None = None
        self._repository: AuthRepository | None = None

        # In-memory caches for performance
        self._tag_role_cache: dict[str, list[str]] = {}
        self._route_cache: dict[str, dict[str, Any]] = {}
        self._route_finder: Callable[[str, str], dict[str, Any] | None] | None = None

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
                supabase_service_key=settings.supabase_service_key,
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
                supabase_service_key=self._config["supabase_service_key"] or "",
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
            # Clear caches
            self._tag_role_cache.clear()
            self._route_cache.clear()
            self._route_finder = None

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
            return {"status": "not_setup", "auth_enabled": False}

        health_status = {
            "status": "healthy",
            "auth_enabled": self._config["auth_enabled"] if self._config else False,
            "tag_role_cache_size": len(self._tag_role_cache),
            "route_cache_size": len(self._route_cache),
        }

        try:
            # Refresh tag-role mappings from Redis
            if self._config and self._config["auth_enabled"]:
                all_tag_data = await sysmap_get(str(MapCategory.TAG_ROLE))
                if all_tag_data:
                    self._tag_role_cache = all_tag_data
                    logger.debug(f"Refreshed tag-role cache with {len(self._tag_role_cache)} entries")
                    # Update the cache size in health status after refresh
                    health_status["tag_role_cache_size"] = len(self._tag_role_cache)

                # Get JWKS cache info if auth client exists
                if self._auth_client:
                    jwks_info = self._auth_client.get_jwks_cache_info()
                    health_status["jwks_cache"] = jwks_info

        except Exception as e:
            logger.error(f"Error during AuthService health check: {e}")
            health_status["status"] = "error"
            health_status["error"] = str(e)

        return health_status

    def collect_router_info(self, app: FastAPI) -> list[dict[str, Any]]:
        """
        Collect all router information from FastAPI app.
        Combines functionality from get_all_endpoints and route finding.
        """
        endpoints: list[dict[str, Any]] = []

        for route in app.routes:
            if isinstance(route, APIRoute):
                endpoint_info = {
                    "path": route.path,
                    "methods": list(route.methods),
                    "tags": route.tags or [],
                    "name": route.name,
                    "endpoint_func": route.endpoint.__name__,
                    "path_template": route.path,
                }
                endpoints.append(endpoint_info)

        return endpoints

    def create_route_finder(self, app: FastAPI) -> Callable[[str, str], dict[str, Any] | None]:
        """
        Create a cached route finder function for fast route matching.
        Replaces the make_route_finder functionality from middlewares.
        """

        @lru_cache(maxsize=4096)
        def _find_route(method: str, path: str) -> dict[str, Any] | None:
            scope = {"type": "http", "method": method, "path": path, "root_path": getattr(app, "root_path", "")}
            for route in app.routes:
                try:
                    match, child_scope = route.matches(scope)
                except Exception:
                    continue
                if match is Match.FULL:
                    return {
                        "method": method,
                        "path": path,
                        "path_template": getattr(route, "path", None),
                        "tags": getattr(route, "tags", []),
                        "path_params": child_scope.get("path_params", {}) if child_scope else {},
                    }
            return None

        self._route_finder = _find_route
        return _find_route

    def find_route(self, method: str, path: str) -> dict[str, Any] | None:
        """
        Find route information for given method and path using cached finder.
        """
        if not self._route_finder:
            logger.error("Route finder not initialized. Call create_route_finder first.")
            return None
        return self._route_finder(method, path)

    def log_router_info(self, endpoints: list[dict[str, Any]]) -> None:
        """
        Log router information for debugging purposes.
        """
        if self._config and self._config["is_debug"]:
            logger.debug("=========================================================")
            logger.debug("All available URLs:")
            for endpoint in endpoints:
                logger.debug(
                    f"  [{'/'.join(endpoint['methods'])}] {endpoint['path']} - {endpoint['name']} \t# {', '.join(endpoint['tags'])} "
                )
            logger.debug("=========================================================")

    def set_tag_role_mapping(self, tag_role_mapping: dict[str, list[str]]) -> None:
        """
        Set tag-role mapping from external source.
        Allows injection of mappings from outside the auth module.
        """
        self._tag_role_cache.update(tag_role_mapping)
        logger.debug(f"Updated tag-role cache with {len(tag_role_mapping)} mappings")

    def get_tag_role_mapping(self) -> dict[str, list[str]]:
        """
        Get current tag-role mapping.
        """
        return self._tag_role_cache.copy()

    async def get_roles_by_tags(self, tags: list[str]) -> set[str]:
        """
        Return set of roles for a given list of tags.
        Uses in-memory cache for better performance.
        """
        if not tags:
            return set()

        required: set[str] = set()
        for t in tags:
            if t in self._tag_role_cache:
                roles = self._tag_role_cache[t]
                if isinstance(roles, list):
                    r: list[str] = [str(role) for role in roles]
                else:
                    r = [str(roles)]
                logger.debug(f"[RBAC] - tag: {t}, roles: {r}")
                required |= set(r)
            else:
                logger.debug(f"[RBAC] - tag: {t}, roles: []")
        return required

    def clear_tag_role_cache(self) -> None:
        """
        Clear the cached tag-role mappings.
        """
        self._tag_role_cache.clear()

    def is_tag_role_cache_initialized(self) -> bool:
        """
        Check if the tag-role cache has data.
        """
        return len(self._tag_role_cache) > 0

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
                cached_profile_json = await get_user_profile(user_id)
                if cached_profile_json:
                    logger.debug(f"User profile retrieved from Redis cache for user ID: {user_id}")
                    return UserProfileData.model_validate_json(cached_profile_json)
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
                    try:
                        profile_json = db_profile.model_dump_json()
                        cache_success = await set_user_profile(
                            user_id, profile_json, self._config["user_cache_ttl_seconds"] if self._config else 3600
                        )
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
                    try:
                        profile_json = supabase_profile.model_dump_json()
                        cache_success = await set_user_profile(
                            user_id, profile_json, self._config["user_cache_ttl_seconds"] if self._config else 3600
                        )
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
        if not self._auth_client:
            logger.error("AuthService not properly initialized")
            return None
        return await self._auth_client.get_user_by_token(token)

    ###########################################################################
    # Proxy to enable external can call some methods defined in _repository
    ###########################################################################
    async def check_user_onboarding_complete(self, user_id: str) -> bool:
        """
        Check if a user has completed onboarding by checking if they have a profile.
        """
        if not self._repository:
            logger.error("AuthService repository not initialized")
            return False
        return await self._repository.check_user_profile_exists(user_id)

    async def get_user_by_auth_id(self, auth_id: str) -> User | None:
        """Get user from database by Supabase auth ID."""
        if not self._repository:
            logger.error("AuthService repository not initialized")
            return None
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
            if not self._repository:
                logger.error("AuthService repository not initialized")
                return []
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
            if not self._repository:
                logger.error("AuthService repository not initialized")
                return True  # Assume needs update if can't check
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
            if not self._repository:
                logger.error("AuthService repository not initialized")
                return False
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
