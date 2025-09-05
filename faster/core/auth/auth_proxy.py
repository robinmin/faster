import time
from typing import Any, cast

from fastapi import Request
import httpx
import jwt
from supabase import Client, create_client

from ..exceptions import AuthError
from ..redisex import get_jwks_key, get_user_profile, set_jwks_key, set_user_profile
from .models import SupabaseUser, UserIdentityData, UserProfileData

# =============================================================================
# Core Authentication Proxy to Supabase Auth
# =============================================================================


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
        # supabase_client_id: str,
        supabase_audience: str,
        cache_ttl: int = 3600,
        auto_refresh_jwks: bool = True,
    ):
        """Initialize the AuthProxy with configuration."""
        self._supabase_url = supabase_url
        self._supabase_anon_key = supabase_anon_key
        self._supabase_service_key = supabase_service_key
        self._supabase_jwks_url = supabase_jwks_url
        # self._supabase_client_id = supabase_client_id
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

        self._jwks_cache: dict[str, Any] = {}
        self._jwks_last_refresh = 0.0

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

    async def _fetch_jwks_keys(self) -> dict[str, Any]:
        """Fetch JWKS keys from Supabase."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self._supabase_jwks_url)
                _ = response.raise_for_status()
                return dict(response.json())
        except Exception as e:
            raise AuthError(f"Failed to fetch JWKS keys: {e}") from e

    async def _get_jwks_key(self, key_id: str) -> dict[str, Any]:
        """Get JWKS key by ID with caching."""
        # Try cache first
        cached_key = await get_jwks_key(key_id)
        if cached_key:
            return cached_key

        # Check if we need to refresh JWKS
        current_time = time.time()
        if (current_time - self._jwks_last_refresh) > self._cache_ttl:
            jwks_data = await self._fetch_jwks_keys()
            self._jwks_last_refresh = current_time

            # Cache all keys
            for key in jwks_data.get("keys", []):
                _ = await set_jwks_key(key["kid"], key, self._cache_ttl)

        # Try cache again after refresh
        cached_key = await get_jwks_key(key_id)
        if not cached_key:
            raise AuthError(f"JWKS key not found: {key_id}")

        return cached_key

    async def verify_jwt_token(self, token: str) -> dict[str, Any]:
        """Verify JWT token and return payload."""
        try:
            # Decode header to get key ID
            unverified_header = jwt.get_unverified_header(token)
            key_id = unverified_header.get("kid")

            if not key_id:
                raise AuthError("Missing key ID in JWT header")

            # Get JWKS key
            jwks_key = await self._get_jwks_key(key_id)

            # Convert JWKS key to PEM format for verification
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(jwks_key)

            # Verify and decode token
            payload = jwt.decode(
                token,
                str(public_key),
                algorithms=["RS256"],
                audience=self._supabase_audience,
                options={"verify_exp": True, "verify_aud": True},
            )

            return dict(payload)

        except jwt.ExpiredSignatureError as e:
            raise AuthError("Token has expired") from e
        except jwt.InvalidAudienceError as e:
            raise AuthError("Invalid token audience") from e
        except jwt.InvalidTokenError as e:
            raise AuthError(f"Invalid token: {e}") from e
        except Exception as e:
            raise AuthError(f"Token verification failed: {e}") from e

    async def get_user_by_id(self, user_id: str, from_cache: bool = True) -> SupabaseUser:
        """Get user profile by ID with optional caching."""
        if from_cache:
            cached_profile_json = await get_user_profile(user_id)
            if cached_profile_json:
                # Convert JSON string back to SupabaseUser object
                return SupabaseUser.model_validate_json(cached_profile_json)

        try:
            # Fetch from Supabase
            response = self.service_client.auth.admin.get_user_by_id(user_id)
            user_data = response.user

            if not user_data:
                raise AuthError("User not found", status_code=404)

            # Create user profile
            profile = SupabaseUser(
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

            # Cache the profile
            profile_json = profile.model_dump_json()
            _ = await set_user_profile(user_id, profile_json, self._cache_ttl)

            return profile

        except Exception as e:
            if isinstance(e, AuthError):
                raise
            raise AuthError(f"Failed to fetch user profile: {e}") from e

    async def authenticate_token(self, token: str) -> SupabaseUser:
        """Authenticate token and return user profile."""
        # Verify JWT token
        payload = await self.verify_jwt_token(token)

        # Extract user ID from payload
        user_id = payload.get("sub")
        if not user_id:
            raise AuthError("User ID not found in token")

        # Get user profile
        return await self.get_user_by_id(user_id)

    async def refresh_user_cache(self, user_id: str) -> SupabaseUser:
        """Force refresh user profile cache."""
        return await self.get_user_by_id(user_id, from_cache=False)

    async def invalidate_user_cache(self, user_id: str) -> None:
        """Invalidate user profile cache."""
        # This would depend on your cache implementation
        # For now, we'll just fetch fresh data
        _ = await self.get_user_by_id(user_id, from_cache=False)

    def _convert_supabase_user_to_profile(self, supabase_user: SupabaseUser) -> UserProfileData:
        """Convert Supabase User to internal UserProfileData."""
        # Convert identities if they exist
        converted_identities = []
        if hasattr(supabase_user, "identities") and supabase_user.identities:
            for identity in supabase_user.identities:
                converted_identities.append(
                    UserIdentityData(
                        identity_id=getattr(identity, "identity_id", ""),
                        id=getattr(identity, "id", ""),
                        user_id=getattr(identity, "user_id", ""),
                        identity_data=getattr(identity, "identity_data", {}) or {},
                        provider=getattr(identity, "provider", ""),
                        last_sign_in_at=getattr(identity, "last_sign_in_at", None),
                        created_at=getattr(identity, "created_at", None),
                        updated_at=getattr(identity, "updated_at", None),
                    )
                )

        return UserProfileData(
            id=supabase_user.id,
            aud=getattr(supabase_user, "aud", "") or "",
            role=getattr(supabase_user, "role", "") or "",
            email=getattr(supabase_user, "email", "") or "",
            email_confirmed_at=getattr(supabase_user, "email_confirmed_at", None),
            phone=getattr(supabase_user, "phone", None),
            confirmed_at=getattr(supabase_user, "confirmed_at", None),
            last_sign_in_at=getattr(supabase_user, "last_sign_in_at", None),
            is_anonymous=getattr(supabase_user, "is_anonymous", False),
            created_at=getattr(supabase_user, "created_at", None),
            updated_at=getattr(supabase_user, "updated_at", None),
            app_metadata=getattr(supabase_user, "app_metadata", {}) or {},
            user_metadata=getattr(supabase_user, "user_metadata", {}) or {},
            identities=converted_identities,
        )

    async def authenticate_and_convert(self, token: str) -> UserProfileData:
        """Authenticate JWT token and return converted user profile data."""
        supabase_user = await self.authenticate_token(token)
        return self._convert_supabase_user_to_profile(supabase_user)


async def get_current_user(request: Request) -> UserProfileData:
    """Dependency to get current authenticated user."""
    if not hasattr(request.state, "authenticated") or not request.state.authenticated:
        raise AuthError("Authentication required")

    return cast(UserProfileData, request.state.user)


async def get_optional_user(request: Request) -> UserProfileData | None:
    """Dependency to get current user if authenticated, None otherwise."""
    if hasattr(request.state, "user") and request.state.authenticated:
        return cast(UserProfileData, request.state.user)
    return None


# =============================================================================
# Usage Example
# =============================================================================

"""
# Example usage in FastAPI application:

from fastapi import FastAPI, Depends
from supabase_auth import AuthProxy, AuthMiddleware, get_current_user, get_optional_user, require_roles

app = FastAPI()

# Initialize auth proxy
auth_proxy = AuthProxy()

# Add auth middleware
app.add_middleware(AuthMiddleware, auth_proxy=auth_proxy)

@app.get("/protected")
async def protected_endpoint(user: UserProfile = Depends(get_current_user)):
    return {"message": f"Hello {user.email}!", "user_id": user.id}

@app.get("/optional-auth")
async def optional_auth_endpoint(user: Optional[UserProfile] = Depends(get_optional_user)):
    if user:
        return {"message": f"Hello {user.email}!"}
    return {"message": "Hello anonymous user!"}

@app.get("/admin-only")
@require_roles("admin", "super_admin")
async def admin_only_endpoint(user: UserProfile = Depends(get_current_user)):
    return {"message": "Admin access granted!", "user": user.email}

@app.get("/user/{user_id}")
async def get_user_endpoint(
    user_id: str,
    auth: AuthProxy = Depends(get_auth_proxy),
    current_user: UserProfile = Depends(get_current_user)
):
    # Only allow users to access their own data or admins
    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    user_profile = await auth.get_user_by_id(user_id)
    return {"user": asdict(user_profile)}
"""
