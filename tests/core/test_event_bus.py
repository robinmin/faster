from __future__ import annotations

# This must be at the top of the file, before any other imports from `faster`
import os

os.environ["REDIS_PROVIDER"] = "fake"

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import uuid

from pydantic import BaseModel
import pytest

from faster.core.event_bus import Event, EventStatus, event_bus

# Constants for testing
TEST_CHANNEL = "test_channel"
TEST_EVENT_TYPE = "TestEvent"
TEST_SOURCE = "test_app"


class User(BaseModel):
    """Example Pydantic model for payload."""

    id: int
    name: str


@pytest.fixture
def mock_redis_client(mocker: MagicMock) -> MagicMock:
    """Fixture to create a mock Redis client and patch the event_bus."""
    mock_client = MagicMock()
    mock_client.publish = AsyncMock(return_value=1)
    mock_client.subscribe = AsyncMock()
    mocker.patch.object(event_bus, "_redis_client", mock_client)
    return mock_client


class TestEventModel:
    """Tests for the Event BaseModel."""

    def test_event_initialization_with_all_fields(self):
        """
        Tests that an Event can be created with all fields specified.
        """
        # Arrange
        now = datetime.now(timezone.utc)
        payload_data = {"message": "hello"}
        event_id = uuid.uuid4().hex

        # Act
        event = Event[dict](
            event_type=TEST_EVENT_TYPE,
            event_id=event_id,
            timestamp=now,
            status=EventStatus.COMPLETED,
            source=TEST_SOURCE,
            payload=payload_data,
            metadata={"correlation_id": "corr-123"},
        )

        # Assert
        assert event.event_type == TEST_EVENT_TYPE
        assert event.event_id == event_id
        assert event.timestamp == now
        assert event.status == EventStatus.COMPLETED
        assert event.source == TEST_SOURCE
        assert event.payload == payload_data
        assert event.metadata == {"correlation_id": "corr-123"}

    def test_event_initialization_with_default_values(self):
        """
        Tests that an Event is created with correct default values
        when optional fields are not provided.
        """

        # Arrange
        class MyEvent(Event[dict]): ...

        # Act
        event = MyEvent(payload={"data": "value"})

        # Assert
        assert event.event_type == "MyEvent"
        assert isinstance(uuid.UUID(event.event_id, version=4), uuid.UUID)
        assert isinstance(event.timestamp, datetime)
        assert (datetime.now(timezone.utc) - event.timestamp).total_seconds() < 1
        assert event.status == EventStatus.PENDING
        assert event.source == "app"
        assert event.payload == {"data": "value"}
        assert event.metadata == {}

    def test_event_initialization_with_empty_payload_defaults_to_dict(self):
        """
        Tests that an Event payload defaults to an empty dictionary if not provided.
        """
        # Arrange & Act
        event = Event[dict](event_type=TEST_EVENT_TYPE)

        # Assert
        assert event.payload == {}

    @pytest.mark.parametrize(
        "payload",
        [
            {"message": "hello world"},
            User(id=1, name="John Doe"),
            [1, "test", True],
            "a simple string",
            42,
        ],
    )
    def test_event_serialization_with_various_payloads(self, payload: Any):
        """
        Tests that an Event can be serialized to JSON with different payload types.
        """
        # Arrange
        event = Event[Any](event_type=TEST_EVENT_TYPE, payload=payload)

        # Act
        json_output = event.model_dump_json()
        data = json.loads(json_output)

        # Assert
        assert data["event_type"] == TEST_EVENT_TYPE
        if isinstance(payload, BaseModel):
            assert data["payload"] == payload.model_dump()
        else:
            assert data["payload"] == payload


@pytest.mark.asyncio
class TestEventBus:
    """Tests for the EventBus."""

    async def test_fire_event_uses_event_type_as_default_channel(self, mock_redis_client: MagicMock):
        """
        Tests that fire_event uses the event's type as the default channel
        if no channel is specified.
        """
        # Arrange
        event = Event[dict](event_type=TEST_EVENT_TYPE, payload={})

        # Act
        await event_bus.fire_event(event)

        # Assert
        mock_redis_client.publish.assert_awaited_once()
        args, _ = mock_redis_client.publish.call_args
        assert args[0] == TEST_EVENT_TYPE
        assert isinstance(args[1], str)

    async def test_fire_event_uses_provided_channel(self, mock_redis_client: MagicMock):
        """
        Tests that fire_event uses the explicitly provided channel for publishing.
        """
        # Arrange
        event = Event[dict](event_type=TEST_EVENT_TYPE, payload={})

        # Act
        await event_bus.fire_event(event, channel=TEST_CHANNEL)

        # Assert
        mock_redis_client.publish.assert_awaited_once_with(TEST_CHANNEL, event.model_dump_json())

    async def test_fire_event_returns_publish_result(self, mock_redis_client: MagicMock):
        """
        Tests that fire_event returns the result from the redis_manager's
        publish call.
        """
        # Arrange
        mock_redis_client.publish.return_value = 5  # Simulate 5 subscribers
        event = Event[dict](event_type=TEST_EVENT_TYPE, payload={})

        # Act
        result = await event_bus.fire_event(event)

        # Assert
        assert result == 5

    async def test_process_events_yields_correctly_decoded_events(self, mock_redis_client: MagicMock):
        """
        Tests that process_events correctly subscribes, listens, and yields
        deserialized Event objects.
        """
        # Arrange
        event_data = {
            "event_type": "UserCreated",
            "event_id": uuid.uuid4().hex,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "source": "auth_service",
            "payload": {"user_id": 123},
        }
        message = {
            "type": "message",
            "data": json.dumps(event_data).encode("utf-8"),
        }

        async def message_generator() -> AsyncGenerator[dict, None]:
            yield message

        mock_pubsub = MagicMock()
        mock_pubsub.listen.return_value = message_generator()
        mock_redis_client.subscribe.return_value = mock_pubsub

        # Act
        processed_events = [ev async for ev in event_bus.process_events(TEST_CHANNEL)]

        # Assert
        mock_redis_client.subscribe.assert_awaited_once_with(TEST_CHANNEL)
        assert len(processed_events) == 1
        event = processed_events[0]
        assert event.event_type == event_data["event_type"]
        assert event.payload == event_data["payload"]

    async def test_process_events_handles_json_decode_error(self, mock_redis_client: MagicMock, mocker: MagicMock):
        """
        Tests that process_events logs an error and continues if a message
        is not valid JSON.
        """
        # Arrange
        invalid_message = {"type": "message", "data": b"this is not json"}

        async def message_generator() -> AsyncGenerator[dict, None]:
            yield invalid_message

        mock_pubsub = MagicMock()
        mock_pubsub.listen.return_value = message_generator()
        mock_redis_client.subscribe.return_value = mock_pubsub
        mock_logger = mocker.patch("faster.core.event_bus.logger")

        # Act
        processed_events = [ev async for ev in event_bus.process_events(TEST_CHANNEL)]

        # Assert
        assert len(processed_events) == 0
        mock_logger.error.assert_called_once_with(f"Failed to decode event message: {invalid_message['data']}")

    async def test_process_events_handles_general_exception(self, mock_redis_client: MagicMock, mocker: MagicMock):
        """
        Tests that process_events logs an error and continues if an unexpected
        exception occurs during event processing.
        """
        # Arrange
        mock_event_class = mocker.patch("faster.core.event_bus.Event")
        mock_event_class.__getitem__.return_value.side_effect = Exception("Unexpected processing error")

        event_data = {"event_type": "AnyEvent", "payload": {"data": "some_data"}}
        message = {"type": "message", "data": json.dumps(event_data)}

        async def message_generator() -> AsyncGenerator[dict, None]:
            yield message

        mock_pubsub = MagicMock()
        mock_pubsub.listen.return_value = message_generator()
        mock_redis_client.subscribe.return_value = mock_pubsub
        mock_logger = mocker.patch("faster.core.event_bus.logger")

        # Act
        processed_events = [ev async for ev in event_bus.process_events(TEST_CHANNEL)]

        # Assert
        assert len(processed_events) == 0
        mock_logger.error.assert_called_once()
        assert "Error processing event: " in mock_logger.error.call_args[0][0]

    async def test_process_events_handles_subscription_failure(self, mock_redis_client: MagicMock, mocker: MagicMock):
        """
        Tests that process_events logs a warning if the subscription to a
        channel fails.
        """
        # Arrange
        mock_redis_client.subscribe.return_value = None
        mock_logger = mocker.patch("faster.core.event_bus.logger")

        # Act
        async def consume():
            return [ev async for ev in event_bus.process_events(TEST_CHANNEL)]

        result = await asyncio.wait_for(consume(), timeout=0.1)

        # Assert
        assert result == []
        mock_logger.warning.assert_called_once_with(f"Failed to subscribe to channel: {TEST_CHANNEL}")
