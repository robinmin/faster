from collections.abc import Mapping
from typing import Any, Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.background import BackgroundTask

from .logger import get_logger

###############################################################################
# models:
#
# Use to define all non-database related entities only(NEVER add any business logic).
#
###############################################################################

logger = get_logger(__name__)
T = TypeVar("T")


class APIContent(BaseModel, Generic[T]):
    """Base response model for all API responses."""

    status: str = "success"
    message: str | None = None
    data: T | None = None
    meta: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class AppResponse(JSONResponse, Generic[T]):
    media_type = "application/json"

    def __init__(
        self,
        status: str = "success",
        message: str | None = None,
        data: T | None = None,
        meta: dict[str, Any] | None = None,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | None = None,
    ) -> None:
        content = APIContent(status=status or "success", message=message or "", data=data or {}, meta=meta or {})
        super().__init__(content.model_dump_json(), status_code, headers, media_type, background)

    def render(self, content: str) -> bytes:
        # The content is already a JSON string from model_dump_json, so just encode it
        return content.encode("utf-8")


AppResponseDict = AppResponse[dict[str, Any]]


###############################################################################
# Request/Response Models for Metadata Management
###############################################################################


class SysDictItem(BaseModel):
    """Model for a single SysDict item."""

    category: str = Field(..., description="Dictionary category")
    key: int = Field(..., description="Dictionary key")
    value: str = Field(..., description="Dictionary value")
    in_used: bool = Field(True, description="Whether the item is active")


class SysMapItem(BaseModel):
    """Model for a single SysMap item."""

    category: str = Field(..., description="Map category")
    left_value: str = Field(..., description="Left side value for mapping")
    right_value: str = Field(..., description="Right side value for mapping")
    in_used: bool = Field(True, description="Whether the item is active")


class SysDictAdjustRequest(BaseModel):
    """Request model for adjusting SysDict entries."""

    category: str = Field(..., description="Dictionary category")
    items: list[SysDictItem] = Field(..., description="List of dictionary items to set")


class SysMapAdjustRequest(BaseModel):
    """Request model for adjusting SysMap entries."""

    category: str = Field(..., description="Map category")
    items: list[SysMapItem] = Field(..., description="List of map items to set")


class SysDictDeleteRequest(BaseModel):
    """Request model for deleting a specific SysDict entry."""

    category: str = Field(..., description="Dictionary category")
    key: int = Field(..., description="Dictionary key")
    value: str = Field(..., description="Dictionary value")


class SysMapDeleteRequest(BaseModel):
    """Request model for deleting a specific SysMap entry."""

    category: str = Field(..., description="Map category")
    left_value: str = Field(..., description="Left side value for mapping")
    right_value: str = Field(..., description="Right side value for mapping")


class SysDictShowRequest(BaseModel):
    """Request model for showing SysDict entries with optional filters."""

    category: str | None = Field(None, description="Filter by dictionary category")
    key: int | None = Field(None, description="Filter by dictionary key")
    value: str | None = Field(None, description="Filter by dictionary value")
    in_used_only: bool = Field(False, description="Show only active entries")


class SysMapShowRequest(BaseModel):
    """Request model for showing SysMap entries with optional filters."""

    category: str | None = Field(None, description="Filter by map category")
    left_value: str | None = Field(None, description="Filter by left side value")
    right_value: str | None = Field(None, description="Filter by right side value")
    in_used_only: bool = Field(False, description="Show only active entries")
