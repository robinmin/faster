from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio.client import Pipeline, PubSub
from redis.asyncio.lock import Lock

from faster.core.redis import (
    RedisManager,
    cached,
    get_redis,
    locked,
)
from faster.core.redis import (
    redis_manager as global_redis_manager,
)
from faster.core.schemas import Event, EventBus, subscribe_events


@pytest.fixture
def mock_redis_client() -> MagicMock:
    """Fixture to create a mock Redis client."""
    client = MagicMock()
    client.ping = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value="test_value")
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.exists = AsyncMock(return_value=1)
    client.expire = AsyncMock(return_value=True)
    client.ttl = AsyncMock(return_value=60)
    client.incr = AsyncMock(return_value=1)
    client.decr = AsyncMock(return_value=0)
    client.hset = AsyncMock(return_value=1)
    client.hget = AsyncMock(return_value="field_value")
    client.hgetall = AsyncMock(return_value={"field": "value"})
    client.hdel = AsyncMock(return_value=1)
    client.lpush = AsyncMock(return_value=1)
    client.rpush = AsyncMock(return_value=1)
    client.lpop = AsyncMock(return_value="list_item")
    client.rpop = AsyncMock(return_value="list_item")
    client.lrange = AsyncMock(return_value=["item1", "item2"])
    client.llen = AsyncMock(return_value=2)
    client.sadd = AsyncMock(return_value=1)
    client.srem = AsyncMock(return_value=1)
    client.smembers = AsyncMock(return_value={"member1", "member2"})
    client.sismember = AsyncMock(return_value=True)
    client.publish = AsyncMock(return_value=1)

    # Mock lock
    mock_lock = AsyncMock(spec=Lock)
    mock_lock.acquire = AsyncMock(return_value=True)
    mock_lock.release = AsyncMock()
    client.lock = MagicMock(return_value=mock_lock)

    # Mock pubsub
    mock_pubsub = AsyncMock(spec=PubSub)
    client.pubsub = MagicMock(return_value=mock_pubsub)

    # Mock pipeline
    mock_pipeline = MagicMock(spec=Pipeline)
    client.pipeline = MagicMock(return_value=mock_pipeline)

    return client


@pytest.fixture
def redis_manager(mock_redis_client: MagicMock) -> RedisManager:
    """Fixture to create a RedisManager instance with a mock client."""
    global_redis_manager._client = mock_redis_client
    global_redis_manager._pool = MagicMock()  # Mock the pool as well
    return global_redis_manager


@pytest.mark.asyncio
async def test_get_client_uninitialized():
    """Test that _get_client raises an error if the client is not initialized."""
    manager = RedisManager()
    with pytest.raises(ConnectionError, match="Redis client is not initialized."):
        manager._get_client()


@pytest.mark.asyncio
async def test_ping(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the ping method."""
    result = await redis_manager.ping()
    assert result is True
    mock_redis_client.ping.assert_called_once()


@pytest.mark.asyncio
async def test_get(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the get method."""
    result = await redis_manager.get("test_key")
    assert result == "test_value"
    mock_redis_client.get.assert_called_once_with("test_key")


@pytest.mark.asyncio
async def test_set_value(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the set_value method."""
    result = await redis_manager.set_value("test_key", "test_value", expire=60)
    assert result is True
    mock_redis_client.set.assert_called_once_with("test_key", "test_value", ex=60)


@pytest.mark.asyncio
async def test_delete(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the delete method."""
    result = await redis_manager.delete("key1", "key2")
    assert result == 1
    mock_redis_client.delete.assert_called_once_with("key1", "key2")


@pytest.mark.asyncio
async def test_exists(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the exists method."""
    result = await redis_manager.exists("key1", "key2")
    assert result == 1
    mock_redis_client.exists.assert_called_once_with("key1", "key2")


@pytest.mark.asyncio
async def test_expire(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the expire method."""
    result = await redis_manager.expire("test_key", 120)
    assert result is True
    mock_redis_client.expire.assert_called_once_with("test_key", 120)


@pytest.mark.asyncio
async def test_ttl(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the ttl method."""
    result = await redis_manager.ttl("test_key")
    assert result == 60
    mock_redis_client.ttl.assert_called_once_with("test_key")


@pytest.mark.asyncio
async def test_incr(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the incr method."""
    result = await redis_manager.incr("counter", amount=2)
    assert result == 1
    mock_redis_client.incr.assert_called_once_with("counter", amount=2)


@pytest.mark.asyncio
async def test_decr(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the decr method."""
    result = await redis_manager.decr("counter", amount=2)
    assert result == 0
    mock_redis_client.decr.assert_called_once_with("counter", amount=2)


@pytest.mark.asyncio
async def test_hset(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the hset method."""
    result = await redis_manager.hset("hash_key", key="field", value="val")
    assert result == 1
    mock_redis_client.hset.assert_called_once_with("hash_key", key="field", value="val", mapping=None)


@pytest.mark.asyncio
async def test_hget(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the hget method."""
    result = await redis_manager.hget("hash_key", "field")
    assert result == "field_value"
    mock_redis_client.hget.assert_called_once_with("hash_key", "field")


@pytest.mark.asyncio
async def test_hgetall(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the hgetall method."""
    result = await redis_manager.hgetall("hash_key")
    assert result == {"field": "value"}
    mock_redis_client.hgetall.assert_called_once_with("hash_key")


@pytest.mark.asyncio
async def test_hdel(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the hdel method."""
    result = await redis_manager.hdel("hash_key", "field1", "field2")
    assert result == 1
    mock_redis_client.hdel.assert_called_once_with("hash_key", "field1", "field2")


@pytest.mark.asyncio
async def test_lpush(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the lpush method."""
    result = await redis_manager.lpush("list_key", "val1", "val2")
    assert result == 1
    mock_redis_client.lpush.assert_called_once_with("list_key", "val1", "val2")


@pytest.mark.asyncio
async def test_rpush(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the rpush method."""
    result = await redis_manager.rpush("list_key", "val1", "val2")
    assert result == 1
    mock_redis_client.rpush.assert_called_once_with("list_key", "val1", "val2")


@pytest.mark.asyncio
async def test_lpop(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the lpop method."""
    result = await redis_manager.lpop("list_key")
    assert result == "list_item"
    mock_redis_client.lpop.assert_called_once_with("list_key")


@pytest.mark.asyncio
async def test_rpop(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the rpop method."""
    result = await redis_manager.rpop("list_key")
    assert result == "list_item"
    mock_redis_client.rpop.assert_called_once_with("list_key")


@pytest.mark.asyncio
async def test_lrange(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the lrange method."""
    result = await redis_manager.lrange("list_key", 0, -1)
    assert result == ["item1", "item2"]
    mock_redis_client.lrange.assert_called_once_with("list_key", 0, -1)


@pytest.mark.asyncio
async def test_llen(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the llen method."""
    result = await redis_manager.llen("list_key")
    assert result == 2
    mock_redis_client.llen.assert_called_once_with("list_key")


@pytest.mark.asyncio
async def test_sadd(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the sadd method."""
    result = await redis_manager.sadd("set_key", "mem1", "mem2")
    assert result == 1
    mock_redis_client.sadd.assert_called_once_with("set_key", "mem1", "mem2")


@pytest.mark.asyncio
async def test_srem(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the srem method."""
    result = await redis_manager.srem("set_key", "mem1", "mem2")
    assert result == 1
    mock_redis_client.srem.assert_called_once_with("set_key", "mem1", "mem2")


@pytest.mark.asyncio
async def test_smembers(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the smembers method."""
    result = await redis_manager.smembers("set_key")
    assert result == {"member1", "member2"}
    mock_redis_client.smembers.assert_called_once_with("set_key")


@pytest.mark.asyncio
async def test_sismember(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the sismember method."""
    result = await redis_manager.sismember("set_key", "member1")
    assert result is True
    mock_redis_client.sismember.assert_called_once_with("set_key", "member1")


@pytest.mark.asyncio
async def test_acquire_lock(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the acquire_lock method."""
    lock = await redis_manager.acquire_lock("lock_key", timeout=10)
    assert lock is not None
    mock_redis_client.lock.assert_called_once_with("lock_key", timeout=10)
    lock.acquire.assert_called_once_with(blocking=True)


@pytest.mark.asyncio
async def test_release_lock(redis_manager: RedisManager):
    """Test the release_lock method."""
    mock_lock = MagicMock(spec=Lock)
    mock_lock.release = AsyncMock()
    await redis_manager.release_lock(mock_lock)
    mock_lock.release.assert_called_once()


@pytest.mark.asyncio
async def test_publish(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the publish method."""
    result = await redis_manager.publish("channel", "message")
    assert result == 1
    mock_redis_client.publish.assert_called_once_with("channel", "message")


@pytest.mark.asyncio
async def test_subscribe(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the subscribe method."""
    pubsub = await redis_manager.subscribe("channel1", "channel2")
    assert pubsub is not None
    mock_redis_client.pubsub.assert_called_once_with(ignore_subscribe_messages=True)
    pubsub.subscribe.assert_called_once_with("channel1", "channel2")


@pytest.mark.asyncio
async def test_pipeline(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the pipeline method."""
    pipeline = redis_manager.pipeline(transaction=False)
    assert pipeline is not None
    mock_redis_client.pipeline.assert_called_once_with(transaction=False)


@pytest.mark.asyncio
async def test_health_check_success(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the health_check method for a success case."""
    mock_redis_client.ping.return_value = True
    result = await redis_manager.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_health_check_failure(redis_manager: RedisManager, mock_redis_client: MagicMock):
    """Test the health_check method for a failure case."""
    mock_redis_client.ping.side_effect = ConnectionError("Connection failed")
    result = await redis_manager.health_check()
    assert result is False


@pytest.mark.asyncio
@patch("faster.core.redis.redis_manager", new_callable=AsyncMock)
async def test_get_redis_dependency(mock_manager: AsyncMock):
    """Test the get_redis dependency."""
    # The dependency is an async generator, so we need to treat it as such
    gen = get_redis()
    # Get the yielded value
    manager_instance = await gen.__anext__()  # noqa: F841
    # Check if the context manager methods were called
    mock_manager.__aenter__.assert_called_once()
    # Simulate the 'with' block finishing
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()
    # Check that the exit method was called
    mock_manager.__aexit__.assert_called_once()


@pytest.mark.asyncio
@patch("faster.core.redis.redis_manager")
async def test_cached_cache_hit(mock_redis_manager: MagicMock):
    """Test the cached decorator when there is a cache hit."""
    mock_redis_manager.get = AsyncMock(return_value=json.dumps({"data": "cached_value"}))
    mock_redis_manager.set_value = AsyncMock()

    @cached(expire=60, key_prefix="test_cache")
    async def test_function(arg1: str):
        return {"data": f"computed_value_{arg1}"}

    result = await test_function("test_arg")

    assert result == {"data": "cached_value"}
    mock_redis_manager.get.assert_called_once()
    mock_redis_manager.set_value.assert_not_called()


@pytest.mark.asyncio
@patch("faster.core.redis.redis_manager")
async def test_cached_cache_miss(mock_redis_manager: MagicMock):
    """Test the cached decorator when there is a cache miss."""
    mock_redis_manager.get = AsyncMock(return_value=None)
    mock_redis_manager.set_value = AsyncMock(return_value=True)

    @cached(expire=60, key_prefix="test_cache")
    async def test_function(arg1: str):
        return {"data": f"computed_value_{arg1}"}

    result = await test_function("test_arg")

    assert result == {"data": "computed_value_test_arg"}
    mock_redis_manager.get.assert_called_once()
    mock_redis_manager.set_value.assert_called_once()


@pytest.mark.asyncio
@patch("faster.core.redis.redis_manager")
async def test_cached_with_key_builder(mock_redis_manager: MagicMock):
    """Test the cached decorator with a custom key_builder."""
    mock_redis_manager.get = AsyncMock(return_value=None)
    mock_redis_manager.set_value = AsyncMock(return_value=True)

    def custom_key_builder(arg1: str, arg2: int):
        return f"custom_key:{arg1}:{arg2}"

    @cached(expire=60, key_builder=custom_key_builder)
    async def test_function(arg1: str, arg2: int):
        return {"data": f"computed_value_{arg1}_{arg2}"}

    result = await test_function("test_arg", 123)

    expected_key = "custom_key:test_arg:123"
    assert result == {"data": "computed_value_test_arg_123"}
    mock_redis_manager.get.assert_called_once_with(expected_key)
    mock_redis_manager.set_value.assert_called_once_with(expected_key, json.dumps(result), 60)


@pytest.mark.asyncio
@patch("faster.core.redis.redis_manager")
async def test_cached_json_decode_error(mock_redis_manager: MagicMock):
    """Test cached decorator handles JSONDecodeError and recomputes."""
    mock_redis_manager.get = AsyncMock(return_value="invalid json string")
    mock_redis_manager.set_value = AsyncMock(return_value=True)

    @cached(expire=60, key_prefix="test_cache")
    async def test_function(arg1: str):
        return {"data": f"recomputed_value_{arg1}"}

    result = await test_function("test_arg")

    assert result == {"data": "recomputed_value_test_arg"}
    mock_redis_manager.get.assert_called_once()
    mock_redis_manager.set_value.assert_called_once()


@pytest.mark.asyncio
@patch("faster.core.redis.redis_manager")
async def test_locked_success(mock_redis_manager: MagicMock):
    """Test the locked decorator when the lock is successfully acquired."""
    mock_lock = AsyncMock(spec=Lock)
    mock_lock.acquire.return_value = True
    mock_lock.release = AsyncMock()
    mock_redis_manager.acquire_lock = AsyncMock(return_value=mock_lock)
    mock_redis_manager.release_lock = AsyncMock()

    @locked(lock_name="my_specific_lock", timeout=5)
    async def protected_function():
        return "function_executed"

    result = await protected_function()

    assert result == "function_executed"
    mock_redis_manager.acquire_lock.assert_called_once_with("my_specific_lock", timeout=5)
    mock_redis_manager.release_lock.assert_called_once_with(mock_lock)


@pytest.mark.asyncio
@patch("faster.core.redis.redis_manager")
async def test_locked_failure_proceeds(mock_redis_manager: MagicMock):
    """Test the locked decorator when lock acquisition fails, but function still proceeds."""
    mock_redis_manager.acquire_lock = AsyncMock(return_value=None)
    mock_redis_manager.release_lock = AsyncMock()

    @locked(lock_name="my_specific_lock")
    async def protected_function():
        return "function_executed_without_lock"

    result = await protected_function()

    assert result == "function_executed_without_lock"
    mock_redis_manager.acquire_lock.assert_called_once_with("my_specific_lock", timeout=None)
    mock_redis_manager.release_lock.assert_not_called()


@pytest.mark.asyncio
@patch("faster.core.redis.redis_manager")
async def test_locked_default_lock_name(mock_redis_manager: MagicMock):
    """Test the locked decorator uses default lock name if not provided."""
    mock_lock = AsyncMock(spec=Lock)
    mock_lock.acquire.return_value = True
    mock_lock.release = AsyncMock()
    mock_redis_manager.acquire_lock = AsyncMock(return_value=mock_lock)
    mock_redis_manager.release_lock = AsyncMock()

    @locked()
    async def another_protected_function():
        return "default_lock_name_test"

    result = await another_protected_function()

    assert result == "default_lock_name_test"
    mock_redis_manager.acquire_lock.assert_called_once_with("lock:another_protected_function", timeout=None)
    mock_redis_manager.release_lock.assert_called_once_with(mock_lock)


@pytest.mark.asyncio
@patch("faster.core.redis.redis_manager")
async def test_locked_exception_handling(mock_redis_manager: MagicMock):
    """Test the locked decorator releases lock even if decorated function raises an exception."""
    mock_lock = AsyncMock(spec=Lock)
    mock_lock.acquire.return_value = True
    mock_lock.release = AsyncMock()
    mock_redis_manager.acquire_lock = AsyncMock(return_value=mock_lock)
    mock_redis_manager.release_lock = AsyncMock()

    class CustomError(Exception):
        pass

    @locked(lock_name="error_lock")
    async def error_function():
        raise CustomError("Something went wrong")

    with pytest.raises(CustomError):
        await error_function()

    mock_redis_manager.acquire_lock.assert_called_once()
    mock_redis_manager.release_lock.assert_called_once_with(mock_lock)


@pytest.mark.asyncio
@patch("faster.core.schemas.redis_manager")
async def test_event_bus_fire_event(mock_redis_manager: MagicMock):
    """Test firing an event via EventBus."""
    mock_redis_manager.publish = AsyncMock()

    event_bus_instance = EventBus(mock_redis_manager)
    test_event = Event(event_type="user_created", payload={"id": 1, "name": "test"})

    await event_bus_instance.fire_event("user_channel", test_event)

    mock_redis_manager.publish.assert_called_once_with("user_channel", test_event.model_dump_json())


@pytest.mark.asyncio
@patch("faster.core.schemas.redis_manager")
async def test_event_bus_process_events(mock_redis_manager: MagicMock):
    """Test processing events via EventBus."""
    mock_pubsub = AsyncMock(spec=PubSub)
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()

    # Simulate two messages, then no more
    mock_pubsub.get_message.side_effect = [
        {
            "channel": "test_channel",
            "data": json.dumps({"event_type": "test_event_1", "payload": {"value": 1}}),
            "pattern": None,
        },
        {
            "channel": "test_channel",
            "data": json.dumps({"event_type": "test_event_2", "payload": {"value": 2}}),
            "pattern": None,
        },
        None,  # Simulate no more messages after two events
    ]

    mock_redis_manager.subscribe = AsyncMock(return_value=mock_pubsub)

    event_bus_instance = EventBus(mock_redis_manager)
    received_events = []

    async for event in event_bus_instance.process_events("test_channel"):
        received_events.append(event)

    assert len(received_events) == 2
    assert received_events[0].event_type == "test_event_1"
    assert received_events[0].payload == {"value": 1}
    assert received_events[1].event_type == "test_event_2"
    assert received_events[1].payload == {"value": 2}

    mock_redis_manager.subscribe.assert_called_once_with("test_channel")
    mock_pubsub.subscribe.assert_called_once_with("test_channel")
    mock_pubsub.unsubscribe.assert_called_once_with("test_channel")
    mock_pubsub.close.assert_called_once()


@pytest.mark.asyncio
@patch("faster.core.schemas.redis_manager")
async def test_event_bus_process_events_no_pubsub(mock_redis_manager: MagicMock):
    """Test processing events when pubsub object is not returned."""
    mock_redis_manager.subscribe = AsyncMock(return_value=None)

    event_bus_instance = EventBus(mock_redis_manager)
    received_events = []

    # The process_events method should return without yielding if pubsub is None
    # We can simply iterate over it and expect no events.
    async for event in event_bus_instance.process_events("test_channel"):
        received_events.append(event)

    assert len(received_events) == 0
    mock_redis_manager.subscribe.assert_called_once_with("test_channel")


@pytest.mark.asyncio
@patch("faster.core.schemas.redis_manager")
async def test_event_bus_process_events_json_decode_error(
    mock_redis_manager: MagicMock,
):
    """Test processing events handles JSONDecodeError for invalid messages."""
    mock_pubsub = AsyncMock(spec=PubSub)
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()

    mock_pubsub.get_message.side_effect = [
        {"channel": "test_channel", "data": "invalid json", "pattern": None},
        None,  # Stop after the invalid message
    ]

    mock_redis_manager.subscribe = AsyncMock(return_value=mock_pubsub)

    event_bus_instance = EventBus(mock_redis_manager)
    received_events = []

    async for event in event_bus_instance.process_events("test_channel"):
        received_events.append(event)

    assert len(received_events) == 0
    mock_redis_manager.subscribe.assert_called_once_with("test_channel")
    mock_pubsub.unsubscribe.assert_called_once_with("test_channel")
    mock_pubsub.close.assert_called_once()


@pytest.mark.asyncio
@patch("faster.core.schemas.event_bus")
async def test_subscribe_events_decorator(mock_event_bus: MagicMock):
    """Test the subscribe_events decorator."""

    async def mock_process_events_generator():
        yield Event(event_type="user_created", payload={"id": 1, "name": "test"})
        yield Event(event_type="user_deleted", payload={"id": 1})

    mock_event_bus.process_events.return_value = mock_process_events_generator()

    received_events_in_decorated_function = []

    @subscribe_events(channel="test_channel")
    async def event_handler(event: Event[Any]):
        received_events_in_decorated_function.append(event)

    # Call the decorated function to start processing events
    await event_handler()

    assert len(received_events_in_decorated_function) == 2
    assert received_events_in_decorated_function[0].event_type == "user_created"
    assert received_events_in_decorated_function[1].event_type == "user_deleted"
    mock_event_bus.process_events.assert_called_once_with("test_channel")
