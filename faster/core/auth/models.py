from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field
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

    email: EmailStr = Field(..., description="User's email address.")
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

###############################################################################

class AppMetadata(BaseModel):
    """Schema for app metadata from Supabase Auth."""

    provider: str = Field(default="", description="Authentication provider")
    providers: list[str] = Field(default_factory=list, description="List of authentication providers")

    model_config = ConfigDict(from_attributes=True)


class UserMetadata(BaseModel):
    """Schema for user metadata from Supabase Auth."""

    avatar_url: str | None = Field(default=None, description="User avatar URL")
    email: str | None = Field(default=None, description="User email from provider")
    email_verified: bool | None = Field(default=None, description="Email verification status")
    full_name: str | None = Field(default=None, description="User full name")
    iss: str | None = Field(default=None, description="Token issuer")
    name: str | None = Field(default=None, description="User name")
    phone_verified: bool | None = Field(default=None, description="Phone verification status")
    picture: str | None = Field(default=None, description="User picture URL")
    provider_id: str | None = Field(default=None, description="Provider user ID")
    sub: str | None = Field(default=None, description="Subject identifier")

    model_config = ConfigDict(from_attributes=True)


class UserInfo(BaseModel):
    """Complete user information composed from all auth tables."""

    id: str = Field(..., description="Supabase Auth user ID")
    aud: str = Field(default="", description="JWT audience")
    role: str = Field(default="", description="User role")
    email: str = Field(default="", description="User email")
    email_confirmed_at: datetime | None = Field(default=None, description="Email confirmation timestamp")
    phone: str | None = Field(default=None, description="User phone number")
    confirmed_at: datetime | None = Field(default=None, description="Account confirmation timestamp")
    last_sign_in_at: datetime | None = Field(default=None, description="Last sign in timestamp")
    is_anonymous: bool = Field(default=False, description="Anonymous user flag")
    created_at: datetime | None = Field(default=None, description="Auth creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Auth update timestamp")
    app_metadata: AppMetadata = Field(default_factory=AppMetadata, description="App metadata")
    user_metadata: UserMetadata = Field(default_factory=UserMetadata, description="User metadata")
    identities: list[UserIdentityData] = Field(default_factory=list, description="User identities")
    profile: dict[str, Any] | None = Field(default=None, description="User profile information")

    model_config = ConfigDict(from_attributes=True)
