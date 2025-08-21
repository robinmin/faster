"""Pydantic models for authentication and user management."""

from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Base schema for user properties."""

    email: EmailStr = Field(..., description="User's email address.")


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str = Field(..., min_length=8, description="User's password.")


class UserSignIn(UserBase):
    """Schema for user sign-in."""

    password: str = Field(..., description="User's password.")


class UserUpdate(BaseModel):
    """Schema for updating user information."""

    password: str | None = Field(None, min_length=8, description="New password for the user.")
    data: dict[str, Any] | None = Field(None, description="Additional user metadata.")


class UserRead(UserBase):
    """Schema for reading user information."""

    id: str = Field(..., description="Unique identifier for the user.")

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """Schema for authentication tokens."""

    access_token: str = Field(..., description="JWT access token.")
    refresh_token: str = Field(..., description="Token to refresh the access token.")
    token_type: str = Field(default="bearer", description="Type of the token.")


class MagicLoginRequest(BaseModel):
    """Schema for magic login request."""

    email: EmailStr = Field(..., description="User's email address.")
    token: str = Field(..., description="Magic login token.")


class OAuthSignIn(BaseModel):
    """Schema for OAuth sign-in response."""

    provider: str = Field(..., description="OAuth provider name.")
    url: str = Field(..., description="URL for OAuth sign-in.")


class ResetPasswordRequest(BaseModel):
    """Schema for reset password request."""

    email: EmailStr = Field(..., description="User's email address.")
