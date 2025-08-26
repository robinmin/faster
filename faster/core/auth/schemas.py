from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AuthUser(BaseModel):
    """Schema for authenticated user."""

    email: EmailStr = Field(..., description="User's email address.")
    id: str
    token: str
    raw: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
