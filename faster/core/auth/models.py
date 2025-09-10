from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field
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


class AuthUser(BaseModel):
    """Schema for authenticated user (legacy - consider removing if not used)."""

    email: EmailStr = Field(..., description="User's email address.")
    id: str
    token: str
    raw: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)

###############################################################################
# End of models
###############################################################################
