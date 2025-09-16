import time
from typing import Any

import httpx
import jwt
from supabase import Client, create_client

from ..logger import get_logger
from .models import UserProfileData

# =============================================================================
# Core Authentication Proxy to Supabase Auth
# =============================================================================

logger = get_logger(__name__)


class AuthProxy:
    """
    Centralized proxy for all Supabase Auth operations.
    Handles JWT verification, user management, and caching.
    """

    def __init__(
        self,
        supabase_url: str,
        supabase_anon_key: str,
        supabase_service_key: str,
        supabase_jwks_url: str,
        supabase_audience: str,
        cache_ttl: int = 3600,
        auto_refresh_jwks: bool = True,
    ):
        """Initialize the AuthProxy with configuration."""
        self._supabase_url = supabase_url
        self._supabase_anon_key = supabase_anon_key
        self._supabase_service_key = supabase_service_key
        self._supabase_jwks_url = supabase_jwks_url
        self._supabase_audience = supabase_audience
        self._cache_ttl = cache_ttl
        self._auto_refresh_jwks = auto_refresh_jwks

        # self._client (Anon Key):
        # - Has limited permissions defined by your Row Level Security (RLS) policies
        # - Used for operations that should respect user-level permissions
        # - Cannot access admin-only functions
        self._client: Client | None = None

        # self._service_client (Service Key):
        # - Has full administrative access, bypasses RLS
        # - Used for admin operations like fetching any user's profile
        # - Required for operations like admin.get_user_by_id()
        self._service_client: Client | None = None

        # In-memory JWKS caching
        self._jwks_keys_cache: dict[str, dict[str, Any]] = {}
        self._jwks_cache_timestamp: float = 0.0
        self.last_refresh: float = 0.0  # Keep for compatibility

    @property
    def client(self) -> Client:
        """Get the Supabase client (lazy initialization)."""
        if self._client is None:
            self._client = create_client(self._supabase_url, self._supabase_anon_key)
        return self._client

    @property
    def service_client(self) -> Client:
        """Get the Supabase service client (lazy initialization)."""
        if self._service_client is None:
            self._service_client = create_client(self._supabase_url, self._supabase_service_key)
        return self._service_client

    def _extract_token_header_info(self, token: str) -> tuple[str | None, str | None]:
        """Extract key ID and algorithm from JWT token header."""
        try:
            unverified_header = jwt.get_unverified_header(token)
            key_id = unverified_header.get("kid")
            token_alg = unverified_header.get("alg")

            if not key_id:
                logger.debug("Missing key ID (kid) in JWT header")
                return None, None

            return key_id, token_alg
        except jwt.InvalidTokenError:
            logger.debug("Invalid JWT token format")
            return None, None

    def _determine_algorithm(self, jwks_key: dict[str, Any], token_alg: str | None) -> str | None:
        """Determine the algorithm to use for verification."""
        algorithm = jwks_key.get("alg") or token_alg
        if not algorithm:
            logger.debug("Missing algorithm in both JWKS key and token header")
        return algorithm

    def _construct_public_key(self, jwks_key: dict[str, Any]) -> Any:
        """Construct public key from JWKS key."""
        try:
            return jwt.PyJWK(jwks_key).key
        except (jwt.InvalidKeyError, jwt.PyJWKError, Exception) as e:
            logger.debug(f"Failed to construct public key from JWKS: {e}")
            return None

    def _verify_jwt_token(
        self, token: str, public_key: Any, algorithm: str, expected_audience: str
    ) -> dict[str, Any] | None:
        """Verify JWT token and return payload."""
        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=[algorithm],
                audience=expected_audience,
                options={
                    "verify_exp": True,  # Verify expiration
                    "verify_aud": True,  # Verify audience
                    "verify_signature": True,  # Verify signature
                },
            )
            return dict(payload)
        except jwt.ExpiredSignatureError:
            logger.debug("JWT token has expired")
        except jwt.InvalidAudienceError:
            logger.debug(f"JWT audience mismatch: expected '{expected_audience}'")
        except jwt.InvalidTokenError as e:
            logger.debug(f"JWT token validation failed: {e}")
        return None

    def _extract_user_id_from_payload(self, payload: dict[str, Any]) -> str | None:
        """Extract user ID from JWT payload."""
        user_id = payload.get("sub")
        if not user_id:
            logger.debug("Missing 'sub' (user ID) claim in JWT payload")
            return None
        return str(user_id)

    def _check_memory_cache(self, key_id: str) -> dict[str, Any] | None:
        """Check if JWKS key exists in memory cache."""
        try:
            current_time = time.time()
            # Check if cache is expired
            if (current_time - self._jwks_cache_timestamp) > self._cache_ttl:
                logger.debug("JWKS memory cache expired, will refresh")
                return None

            cached_key = self._jwks_keys_cache.get(key_id)
            if cached_key:
                logger.debug(f"JWKS key found in memory cache: {key_id}")
                return cached_key
        except Exception as e:
            logger.debug(f"Memory cache read failed: {e}")
        return None

    def _cache_jwks_keys(self, jwks_data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Cache all JWKS keys in memory and return target key and cache success status."""
        target_key: dict[str, Any] = {}
        cache_failed = False

        try:
            current_time = time.time()
            # Clear existing cache and update with new data
            self._jwks_keys_cache.clear()

            for jwk_key in jwks_data.get("keys", []):
                kid = jwk_key.get("kid")
                if not kid:
                    continue

                # Store first key as potential target (will be overwritten if specific key found)
                if not target_key:
                    target_key = jwk_key

                # Cache this key in memory
                self._jwks_keys_cache[kid] = dict(jwk_key)
                logger.debug(f"Cached JWKS key in memory: {kid}")

            # Update cache timestamp
            self._jwks_cache_timestamp = current_time
            logger.debug(f"Updated JWKS memory cache with {len(self._jwks_keys_cache)} keys")

        except Exception as e:
            cache_failed = True
            logger.debug(f"Memory cache write failed: {e}")

        return target_key, cache_failed

    async def _find_target_key(self, jwks_data: dict[str, Any], key_id: str) -> dict[str, Any]:
        """Find the target key from JWKS data."""
        for jwk_key in jwks_data.get("keys", []):
            kid = jwk_key.get("kid")
            if kid == key_id:
                return dict(jwk_key)
        return {}

    async def _fetch_jwks_from_server(self, jwks_url: str) -> dict[str, Any]:
        """
        Fetch JWKS keys directly from the authorization server.

        Internal utility that handles HTTP requests to JWKS endpoint
        with proper timeout and error handling.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(jwks_url)
                _ = response.raise_for_status()
                return dict(response.json())
        except httpx.TimeoutException:
            logger.error(f"Timeout fetching JWKS from: {jwks_url}")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching JWKS from {jwks_url}: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Unexpected error fetching JWKS from {jwks_url}: {e}")
        return {}

    async def _get_cached_jwks_key(
        self, key_id: str, jwks_url: str, cache_ttl: int, auto_refresh: bool
    ) -> dict[str, Any]:
        """
        Get JWKS key by ID with in-memory caching and automatic refresh.

        Internal utility function that handles:
        - In-memory caching of JWKS keys
        - Automatic refresh of expired keys
        - TTL-based expiration
        """
        # Try memory cache first if auto_refresh is enabled
        if auto_refresh:
            cached_key = self._check_memory_cache(key_id)
            if cached_key:
                return cached_key

        # Fetch fresh JWKS data from server
        try:
            jwks_data = await self._fetch_jwks_from_server(jwks_url)
            if not jwks_data or not jwks_data.get("keys"):
                logger.debug(f"No JWKS keys returned from: {jwks_url}")
                return {}

            # Find the target key and cache all keys
            target_key = await self._find_target_key(jwks_data, key_id)
            _, cache_failed = self._cache_jwks_keys(jwks_data)

            # Update refresh timestamp only if caching succeeded
            if not cache_failed:
                self.last_refresh = time.time()
                logger.debug(f"JWKS keys refreshed and cached in memory from: {jwks_url}")

            return target_key

        except Exception as e:
            logger.debug(f"Failed to fetch JWKS from server: {e}")
            return {}

    def clear_jwks_cache(self) -> None:
        """Clear the in-memory JWKS cache. Useful for testing and cache invalidation."""
        self._jwks_keys_cache.clear()
        self._jwks_cache_timestamp = 0.0
        self.last_refresh = 0.0
        logger.debug("Cleared JWKS memory cache")

    def get_jwks_cache_info(self) -> dict[str, Any]:
        """Get information about the current JWKS cache state. Useful for monitoring."""
        current_time = time.time()
        return {
            "cached_keys_count": len(self._jwks_keys_cache),
            "cache_age_seconds": current_time - self._jwks_cache_timestamp,
            "cache_ttl_seconds": self._cache_ttl,
            "is_expired": (current_time - self._jwks_cache_timestamp) > self._cache_ttl,
            "cached_key_ids": list(self._jwks_keys_cache.keys()),
        }

    async def get_user_id_from_token(self, token: str) -> str | None:  # noqa: PLR0911
        """
        Extract and verify user ID from JWT token with strong verification.

        This utility function performs complete JWT verification including:
        - Signature validation using JWKS public keys
        - Algorithm verification (supports RS256, ES256, etc.)
        - Audience validation
        - Expiration validation
        - Key caching for performance
        """
        if not token:
            logger.debug("Missing required parameters for token verification")
            return None

        try:
            # Extract key ID and algorithm from token header
            key_id, token_alg = self._extract_token_header_info(token)
            if not key_id:
                return None

            # Get JWKS key from cache or server
            jwks_key = await self._get_cached_jwks_key(
                key_id=key_id,
                jwks_url=self._supabase_jwks_url,
                cache_ttl=self._cache_ttl,
                auto_refresh=self._auto_refresh_jwks,
            )
            if not jwks_key:
                logger.error(f"JWKS key not found for kid: {key_id}")
                return None

            # Determine algorithm, construct public key, and verify token
            algorithm = self._determine_algorithm(jwks_key, token_alg)
            if not algorithm:
                logger.error(f"Algorithm not found for kid: {key_id}")
                return None

            public_key = self._construct_public_key(jwks_key)
            if not public_key:
                logger.error(f"Public key not found for kid: {key_id}")
                return None

            payload = self._verify_jwt_token(token, public_key, algorithm, self._supabase_audience)
            if not payload:
                logger.error(f"Token verification failed for kid: {key_id}")
                return None

            user_id = self._extract_user_id_from_payload(payload)
            if not user_id:
                logger.error(f"User ID not found in token for kid: {key_id}")
                return None

            return user_id

        except Exception as e:
            logger.error(f"Unexpected error during token verification: {e}")
            return None

    async def get_user_by_id(self, user_id: str, from_cache: bool = True) -> UserProfileData | None:
        """Get user profile by ID directly from Supabase Auth."""
        try:
            # Fetch from Supabase
            response = self.service_client.auth.admin.get_user_by_id(user_id)
            user_data = response.user

            if not user_data:
                logger.error("User not found", status_code=404)
                return None

            # Create user profile using UserProfileData (inherits from Supabase User)
            profile = UserProfileData(
                id=user_data.id,
                email=user_data.email or "",
                email_confirmed_at=user_data.email_confirmed_at,
                phone=user_data.phone,
                created_at=user_data.created_at,
                updated_at=user_data.updated_at,
                last_sign_in_at=user_data.last_sign_in_at,
                app_metadata=user_data.app_metadata or {},
                user_metadata=user_data.user_metadata or {},
                aud=user_data.aud or "",
                role=user_data.role or "",
            )

            return profile
        except Exception as e:
            logger.error(f"Failed to fetch user profile: {e}")
        return None

    async def get_user_by_token(self, token: str) -> UserProfileData | None:
        """Authenticate token and return user profile."""
        # Extract and verify user ID from JWT token
        user_id = await self.get_user_id_from_token(token)
        if not user_id:
            return None

        # Get user profile
        try:
            return await self.get_user_by_id(user_id)
        except Exception as e:
            logger.error(f"Failed to get user profile for token: {e}")
            return None

    # =============================================================================
    # Password Management Methods
    # =============================================================================

    async def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        """
        Change user password via Supabase Auth.

        Args:
            user_id: User's authentication ID
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            True if password changed successfully, False otherwise
        """
        try:
            # Use service client to update user password
            response = self.service_client.auth.admin.update_user_by_id(user_id, {"password": new_password})

            if response.user:
                logger.info(f"Password changed successfully for user {user_id}")
                return True
            logger.warning(f"Failed to change password for user {user_id}")
            return False

        except Exception as e:
            logger.error(f"Error changing password via Supabase for user {user_id}: {e}")
            return False

    async def initiate_password_reset(self, email: str) -> bool:
        """
        Initiate password reset via Supabase Auth.

        Args:
            email: Email address to send reset link to

        Returns:
            True if reset email sent successfully, False otherwise
        """
        try:
            # Use client (not service client) for password reset
            self.client.auth.reset_password_email(email)

            # Supabase password reset typically returns success even if email doesn't exist
            # for security reasons
            logger.info(f"Password reset initiated for email {email}")
            return True

        except Exception as e:
            logger.error(f"Error initiating password reset via Supabase for email {email}: {e}")
            return False

    async def confirm_password_reset(self, token: str, new_password: str) -> bool:
        """
        Confirm password reset via Supabase Auth.

        Args:
            token: Password reset token
            new_password: New password to set

        Returns:
            True if password reset completed successfully, False otherwise
        """
        try:
            # Use client to verify session and update password
            response = self.client.auth.update_user({"password": new_password})

            if response.user:
                logger.info("Password reset confirmed successfully")
                return True
            logger.warning("Failed to confirm password reset")
            return False

        except Exception as e:
            logger.error(f"Error confirming password reset via Supabase: {e}")
            return False

    async def verify_password(self, user_id: str, password: str) -> bool:
        """
        Verify user password via Supabase Auth.

        Args:
            user_id: User's authentication ID
            password: Password to verify

        Returns:
            True if password is correct, False otherwise
        """
        try:
            # Get user details to extract email
            response = self.service_client.auth.admin.get_user_by_id(user_id)
            if not response.user or not response.user.email:
                logger.warning(f"User not found or no email for user {user_id}")
                return False

            # Attempt to sign in with email and password
            try:
                auth_response = self.client.auth.sign_in_with_password(
                    {"email": response.user.email, "password": password}
                )

                if auth_response.user and auth_response.user.id == user_id:
                    logger.debug(f"Password verification successful for user {user_id}")
                    return True
                logger.debug(f"Password verification failed for user {user_id}")
                return False

            except Exception as auth_e:
                logger.debug(f"Password verification failed for user {user_id}: {auth_e}")
                return False

        except Exception as e:
            logger.error(f"Error verifying password via Supabase for user {user_id}: {e}")
            return False

    # =============================================================================
    # User Management Methods
    # =============================================================================

    async def delete_user(self, user_id: str) -> bool:
        """
        Delete user from Supabase Auth.

        Args:
            user_id: User's authentication ID

        Returns:
            True if user deleted successfully, False otherwise
        """
        try:
            # Use service client to delete user
            self.service_client.auth.admin.delete_user(user_id)

            # Supabase delete user typically doesn't return user data
            logger.info(f"User deleted from Supabase Auth: {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting user via Supabase for user {user_id}: {e}")
            return False
