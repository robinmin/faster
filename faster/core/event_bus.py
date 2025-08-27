from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Generic, TypeVar
import uuid

from pydantic import BaseModel, Field, model_validator

from .logger import get_logger
from .redis import RedisClient, get_redis

logger = get_logger(__name__)

T = TypeVar("T")


class EventStatus(Enum):
    """Enumeration for event statuses."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    SUCCESS = "success"
    PROCESSING = "processing"


class Event(BaseModel, Generic[T]):
    """Base event model for all application events."""

    event_type: str | None = None
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: EventStatus = EventStatus.PENDING
    source: str = "app"
    payload: T | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def set_defaults(cls, data: Any) -> Any:
        """Set dynamic default values before validation."""
        if isinstance(data, dict):
            if "event_type" not in data or data["event_type"] is None:
                data["event_type"] = cls.__name__
            if "payload" not in data or data["payload"] is None:
                data["payload"] = {}
        return data


class EventBus:
    """
    An event bus that uses Redis Pub/Sub to decouple event producers and consumers.
    """

    def __init__(self, redis_client: RedisClient) -> None:
        self._redis_client = redis_client

    async def fire_event(self, event: Event[Any], channel: str | None = None) -> Any:
        """
        Fire an event to a specified channel.
        """
        message = event.model_dump_json()
        event_channel = channel if channel else event.event_type
        if not event_channel:
            raise ValueError("Cannot fire event without a channel or event_type.")
        return await self._redis_client.publish(event_channel, message)

    async def process_events(self, channel: str) -> AsyncGenerator[Event[Any], None]:
        """
        Process events from a specified channel.
        """
        pubsub = await self._redis_client.subscribe(channel)
        if pubsub:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        event_data = json.loads(message["data"])
                        yield Event[Any](**event_data)
                    except json.JSONDecodeError:
                        logger.error(f"Failed to decode event message: {message['data']}")
                    except Exception as e:
                        logger.error(f"Error processing event: {e}")
        else:
            logger.warning(f"Failed to subscribe to channel: {channel}")


# Singleton instance of the EventBus
event_bus = EventBus(get_redis())


# def subscribe_events(channel: str) -> Callable[..., Any]:
#     """
#     A decorator to subscribe a function to a Redis Pub/Sub channel.
#     The decorated function will be called with each event received on the channel.

#     Args:
#         channel: The Redis Pub/Sub channel to subscribe to.

#     Returns:
#         A decorator that subscribes the function to the specified channel.
#     """

#     def decorator(func: Callable[[Event[Any]], Any]) -> Callable[..., Any]:
#         async def wrapper(*args: Any, **kwargs: Any) -> None:
#             async for event in event_bus.process_events(channel):
#                 await func(event)

#         return wrapper

#     return decorator
