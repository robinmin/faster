import asyncio
from collections.abc import AsyncGenerator, Callable, Mapping
import json
import logging
from typing import Any, Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.background import BackgroundTask

from faster.core.redis import RedisManager, redis_manager

logger = logging.getLogger(__name__)

T = TypeVar("T")


class APIContent(BaseModel, Generic[T]):
    """Base response model for all API responses."""

    status: str = "success"
    message: str | None = None
    data: T | None = None
    meta: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class APIResponse(JSONResponse, Generic[T]):
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
        content = APIContent(status=status, message=message, data=data, meta=meta)
        super().__init__(content.model_dump_json(), status_code, headers, media_type, background)

    def render(self, content: str) -> bytes:
        # The content is already a JSON string from model_dump_json, so just encode it
        return content.encode("utf-8")


class Event(BaseModel, Generic[T]):
    """Base event model for all application events."""

    event_type: str
    payload: T


class EventBus:
    """
    An event bus that uses Redis Pub/Sub to decouple event producers and consumers.
    """

    def __init__(self, redis_manager: RedisManager) -> None:
        self._redis_manager = redis_manager

    async def fire_event(self, channel: str, event: Event[Any]) -> int:
        """
        Fires an event to a specified channel.
        """
        message = event.model_dump_json()
        return await self._redis_manager.publish(channel, message)

    async def process_events(self, channel: str) -> AsyncGenerator[Event[Any], None]:
        """
        Subscribes to a channel and yields events as they are received.
        """
        pubsub = await self._redis_manager.subscribe(channel)
        if not pubsub:
            logger.warning(f"Failed to subscribe to channel: {channel}")
            return
        await pubsub.subscribe(channel)  # Ensure subscribe is called on the pubsub object

        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:  # Break if no message received within timeout
                    break
                if message and message["data"]:
                    try:
                        event_data = json.loads(message["data"])
                        yield Event[Any](**event_data)
                    except json.JSONDecodeError:
                        logger.error(f"Failed to decode event message: {message['data']}")
                # Add a small delay to prevent busy-waiting
                await asyncio.sleep(0.01)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()


# Singleton instance of the EventBus
event_bus = EventBus(redis_manager)


def subscribe_events(channel: str) -> Callable[..., Any]:
    """
    A decorator to subscribe a function to a Redis Pub/Sub channel.
    The decorated function will be called with each event received on the channel.

    Args:
        channel: The Redis Pub/Sub channel to subscribe to.

    Returns:
        A decorator that subscribes the function to the specified channel.
    """

    def decorator(func: Callable[[Event[Any]], Any]) -> Callable[..., Any]:
        async def wrapper(*args: Any, **kwargs: Any) -> None:
            async for event in event_bus.process_events(channel):
                await func(event)

        return wrapper

    return decorator
