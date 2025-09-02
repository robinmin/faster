from collections.abc import Mapping
from typing import Any, Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.background import BackgroundTask

from .logger import get_logger

logger = get_logger(__name__)


T = TypeVar("T")


class APIContent(BaseModel, Generic[T]):
    """Base response model for all API responses."""

    status: str = "success"
    message: str | None = None
    data: T | None = None
    meta: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class APIErrorContent(BaseModel):
    """Base response model for all API error responses."""

    status: str = "error"
    message: str | None = None
    errors: list[dict[str, Any]] | None = None

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
