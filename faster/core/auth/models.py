from typing import TypedDict

from supabase_auth.types import User

###############################################################################
# models:
#
# Use to define all non-database related entities only(NEVER add any business logic).
#
###############################################################################


class UserProfileData(User):
    """
    Enhanced user profile model inheriting from Supabase User.

    This is the primary user model used throughout the application for representing
    complete user profile information from Supabase Auth. It includes all standard
    Supabase User fields plus any additional application-specific fields.

    Used for:
    - JWT token authentication and user identification
    - User profile data from Supabase Auth API
    - Internal user representation across services
    - Database storage and caching operations

    Note: This replaces the previous SupabaseUser and UserProfileData models
    to provide a single, consistent user representation.
    """


class AuthServiceConfig(TypedDict):
    """Configuration for AuthService containing only the needed settings."""

    auth_enabled: bool
    supabase_url: str | None
    supabase_anon_key: str | None
    supabase_service_role_key: str | None
    supabase_jwks_url: str | None
    supabase_audience: str | None
    jwks_cache_ttl_seconds: int
    auto_refresh_jwks: bool
    user_cache_ttl_seconds: int
    is_debug: bool


class RouterItem(TypedDict):
    method: str  ## HTTP method
    path: str  ## HTTP request path
    path_template: str  ## Original HTTP request path when declaring the endpoint
    name: str  ## route name
    tags: list[str]  ## tags for this route
    allowed_roles: set[str]  ## allowed roles for this route (set for O(1) membership tests)


###############################################################################
# End of models
###############################################################################
