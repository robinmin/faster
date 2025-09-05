from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr
from pydantic import Field as PydanticField
from supabase_auth.types import User

###############################################################################
# models:
#
# Use to define all non-database related entities only(NEVER add any business logic).
#
###############################################################################

class SupabaseUser(User):
    _placeholder: str = ""


class AuthUser(BaseModel):
    """Schema for authenticated user."""

    email: EmailStr = PydanticField(..., description="User's email address.")
    id: str
    token: str
    raw: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class UserProfileData(BaseModel):
    """Schema for user profile data used internally throughout the application."""

    id: str
    aud: str = ""
    role: str = ""
    email: str = ""
    email_confirmed_at: Any = None
    phone: str | None = None
    confirmed_at: Any = None
    last_sign_in_at: Any = None
    is_anonymous: bool = False
    created_at: Any = None
    updated_at: Any = None
    app_metadata: dict[str, Any] = {}
    user_metadata: dict[str, Any] = {}
    identities: list["UserIdentityData"] = []

    model_config = ConfigDict(from_attributes=True)


class UserIdentityData(BaseModel):
    """Schema for user identity data used internally throughout the application."""

    identity_id: str
    id: str
    user_id: str
    identity_data: dict[str, Any] = {}
    provider: str
    last_sign_in_at: Any = None
    created_at: Any = None
    updated_at: Any = None

    model_config = ConfigDict(from_attributes=True)
