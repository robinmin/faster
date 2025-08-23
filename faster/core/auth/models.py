from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Base schema for user properties."""

    email: EmailStr = Field(..., description="User's email address.")


class AuthUser(UserBase):
    """Schema for authenticated user."""

    id: str
    token: str
    raw: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
