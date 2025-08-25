"""
Comprehensive tests for the RedisManager and its components.
"""

import logging
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from redis.exceptions import ConnectionError, RedisError

from faster.core.redis import (
    RedisClient,
    RedisConnectionError,
    RedisManager,
    RedisOperationError,
    RedisProvider,
    get_redis,
    redis_mgr,
    redis_safe,
    redis_safe_context,
)


# region Fixtures
@pytest.fixture
def manager() -> RedisManager:
    """Provides a clean, uninitialized RedisManager instance for each test."""
    return RedisManager()


@pytest_asyncio.fixture
async def fake_redis_client() -> RedisClient:
    """
    Provides a RedisManager initialized with the 'fake' provider,
    yielding the underlying client.
    """
    await redis_mgr.setup(provider="fake")
    client = redis_mgr.get_client()
    await client.flushdb()  # Ensure clean state
    return client


# endregion


# region Test RedisManager Lifecycle and Setup
class TestRedisManagerSetup:
    """Tests for the setup, close, and state of the RedisManager."""

    def test_initialization(self, manager: RedisManager):
        """
        Arrange: A new RedisManager instance.
        Act: -
        Assert: The client is initially None and not connected.
        """
        assert manager.provider is None
        assert not manager.is_connected
        with pytest.raises(RuntimeError, match="Redis client not initialized"):
            manager.get_client()

    @pytest.mark.asyncio
    async def test_setup_with_fake_provider(self, manager: RedisManager):
        """
        Arrange: An uninitialized RedisManager.
        Act: Call setup with the 'fake' provider.
        Assert: The manager is connected, the provider is FAKE, and the client is available.
        """
        await manager.setup(provider="fake")

        assert manager.is_connected
        assert manager.provider == RedisProvider.FAKE
        client = manager.get_client()
        assert client is not None
        assert await client.ping() is True

    @pytest.mark.asyncio
    async def test_setup_with_invalid_provider_raises_error(self, manager: RedisManager):
        """
        Arrange: An uninitialized RedisManager.
        Act: Call setup with an invalid provider string.
        Assert: ValueError is raised.
        """
        with pytest.raises(ValueError, match="Invalid provider 'invalid'"):
            await manager.setup(provider="invalid")

    @pytest.mark.asyncio
    @patch("faster.core.redis.redis.Redis.from_url")
    async def test_setup_with_url_success(self, mock_from_url, manager: RedisManager):
        """
        Arrange: Mock the underlying redis client to simulate a successful connection.
        Act: Call setup with a URL.
        Assert: The client is created, a ping is sent, and the manager is connected.
        """
        mock_redis_instance = AsyncMock()
        mock_redis_instance.ping.return_value = True
        mock_from_url.return_value = mock_redis_instance

        await manager.setup(provider="local", redis_url="redis://localhost")

        mock_from_url.assert_called_once()
        mock_redis_instance.ping.assert_awaited_once()
        assert manager.is_connected
        assert manager.provider == RedisProvider.LOCAL

    @pytest.mark.asyncio
    @patch("faster.core.redis.redis.Redis.from_url", side_effect=ConnectionError("Failed"))
    async def test_setup_connection_failure_with_fallback_enabled(self, mock_from_url, manager: RedisManager, caplog):
        """
        Arrange: Mock the redis client to raise a ConnectionError.
        Act: Call setup with fallback_to_fake=True (default).
        Assert: An error is logged, and the manager falls back to the fake provider.
        """
        with caplog.at_level(logging.WARNING):
            await manager.setup(provider="local", redis_url="redis://localhost")

        assert "Failed to connect to Redis" in caplog.text
        assert "Falling back to fake Redis" in caplog.text
        assert manager.is_connected
        assert manager.provider == RedisProvider.FAKE

    @pytest.mark.asyncio
    @patch("faster.core.redis.redis.Redis.from_url", side_effect=ConnectionError("Failed"))
    async def test_setup_connection_failure_with_fallback_disabled(self, mock_from_url, manager: RedisManager):
        """
        Arrange: Mock the redis client to raise a ConnectionError.
        Act: Call setup with fallback_to_fake=False.
        Assert: RedisConnectionError is raised.
        """
        with pytest.raises(RedisConnectionError, match="Redis connection failed"):
            await manager.setup(
                provider="local",
                redis_url="redis://localhost",
                fallback_to_fake=False,
            )
        assert not manager.is_connected

    @pytest.mark.asyncio
    async def test_close(self, manager: RedisManager):
        """
        Arrange: A manager connected to a fake provider.
        Act: Call the close method.
        Assert: The client and provider are reset to None, and is_connected is False.
        """
        await manager.setup(provider="fake")
        assert manager.is_connected

        await manager.close()

        assert not manager.is_connected
        assert manager.provider is None
        with pytest.raises(RuntimeError):
            manager.get_client()


# endregion


# region Test RedisClient Operations
@pytest.mark.asyncio
class TestRedisClient:
    """Test suite for all RedisClient methods using a fake Redis backend."""

    async def test_get_set(self, fake_redis_client: RedisClient):
        """Covers GET, SET, and basic existence."""
        # Arrange
        key, value = "test_key", "test_value"

        # Act & Assert (GET on non-existent key)
        assert await fake_redis_client.get(key) is None

        # Act & Assert (SET)
        assert await fake_redis_client.set(key, value) is True
        assert await fake_redis_client.get(key) == value

    async def test_set_with_expiry(self, fake_redis_client: RedisClient):
        """Covers SET with 'ex' parameter and TTL."""
        # Arrange
        key, value = "exp_key", "exp_value"

        # Act
        await fake_redis_client.set(key, value, ex=10)
        ttl = await fake_redis_client.ttl(key)

        # Assert
        assert await fake_redis_client.get(key) == value
        assert 0 < ttl <= 10

    async def test_set_nx_xx(self, fake_redis_client: RedisClient):
        """Covers SET with 'nx' (not exist) and 'xx' (exist) conditions."""
        # Arrange
        key = "cond_key"
        await fake_redis_client.delete(key)  # Ensure key doesn't exist

        # Act & Assert (nx on non-existent key)
        assert await fake_redis_client.set(key, "v1", nx=True) is True
        assert await fake_redis_client.get(key) == "v1"

        # Act & Assert (nx on existent key)
        assert await fake_redis_client.set(key, "v2", nx=True) is False
        assert await fake_redis_client.get(key) == "v1"

        # Act & Assert (xx on existent key)
        assert await fake_redis_client.set(key, "v3", xx=True) is True
        assert await fake_redis_client.get(key) == "v3"

        # Act & Assert (xx on non-existent key)
        await fake_redis_client.delete(key)
        assert await fake_redis_client.set(key, "v4", xx=True) is False
        assert await fake_redis_client.get(key) is None

    async def test_delete(self, fake_redis_client: RedisClient):
        """Covers DELETE on single and multiple keys."""
        # Arrange
        await fake_redis_client.set("k1", "v1")
        await fake_redis_client.set("k2", "v2")
        await fake_redis_client.set("k3", "v3")

        # Act & Assert (delete single)
        assert await fake_redis_client.delete("k1") == 1
        assert await fake_redis_client.get("k1") is None

        # Act & Assert (delete multiple)
        assert await fake_redis_client.delete("k2", "k3") == 2
        assert await fake_redis_client.get("k2") is None
        assert await fake_redis_client.get("k3") is None

        # Act & Assert (delete non-existent)
        assert await fake_redis_client.delete("k4") == 0

    async def test_exists(self, fake_redis_client: RedisClient):
        """Covers EXISTS on single and multiple keys."""
        # Arrange
        await fake_redis_client.set("k1", "v1")
        await fake_redis_client.set("k2", "v2")

        # Act & Assert
        assert await fake_redis_client.exists("k1") == 1
        assert await fake_redis_client.exists("k3") == 0
        assert await fake_redis_client.exists("k1", "k2") == 2
        assert await fake_redis_client.exists("k1", "k3") == 1

    async def test_expire(self, fake_redis_client: RedisClient):
        """Covers EXPIRE."""
        # Arrange
        await fake_redis_client.set("k1", "v1")

        # Act & Assert
        assert await fake_redis_client.expire("k1", 10) is True
        assert 0 < await fake_redis_client.ttl("k1") <= 10
        assert await fake_redis_client.expire("k2", 10) is False

    async def test_hashing(self, fake_redis_client: RedisClient):
        """Covers HSET, HGET, HGETALL, HDEL."""
        # Arrange
        hash_name = "my_hash"
        mapping = {"f1": "v1", "f2": "v2"}

        # Act & Assert (HSET)
        assert await fake_redis_client.hset(hash_name, mapping=mapping) == 2

        # Act & Assert (HGET)
        assert await fake_redis_client.hget(hash_name, "f1") == "v1"
        assert await fake_redis_client.hget(hash_name, "f3") is None

        # Act & Assert (HGETALL)
        assert await fake_redis_client.hgetall(hash_name) == mapping

        # Act & Assert (HDEL)
        assert await fake_redis_client.hdel(hash_name, "f1") == 1
        assert await fake_redis_client.hget(hash_name, "f1") is None
        assert await fake_redis_client.hdel(hash_name, "f3") == 0

    async def test_lists(self, fake_redis_client: RedisClient):
        """Covers LPUSH, RPUSH, LPOP, RPOP, LLEN."""
        # Arrange
        list_name = "my_list"

        # Act & Assert (LPUSH)
        assert await fake_redis_client.lpush(list_name, "a", "b") == 2  # List: [b, a]

        # Act & Assert (RPUSH)
        assert await fake_redis_client.rpush(list_name, "c") == 3  # List: [b, a, c]

        # Act & Assert (LLEN)
        assert await fake_redis_client.llen(list_name) == 3

        # Act & Assert (LPOP)
        assert await fake_redis_client.lpop(list_name) == "b"  # List: [a, c]

        # Act & Assert (RPOP)
        assert await fake_redis_client.rpop(list_name) == "c"  # List: [a]
        assert await fake_redis_client.llen(list_name) == 1

    async def test_sets(self, fake_redis_client: RedisClient):
        """Covers SADD, SMEMBERS, SISMEMBER, SREM."""
        # Arrange
        set_name = "my_set"

        # Act & Assert (SADD)
        assert await fake_redis_client.sadd(set_name, "a", "b", "c") == 3
        assert await fake_redis_client.sadd(set_name, "a") == 0  # Already exists

        # Act & Assert (SMEMBERS)
        members = await fake_redis_client.smembers(set_name)
        assert members == {"a", "b", "c"}

        # Act & Assert (SISMEMBER)
        assert await fake_redis_client.sismember(set_name, "b")
        assert not await fake_redis_client.sismember(set_name, "d")

        # Act & Assert (SREM)
        assert await fake_redis_client.srem(set_name, "c", "d") == 1
        assert await fake_redis_client.smembers(set_name) == {"a", "b"}

    async def test_incr_decr(self, fake_redis_client: RedisClient):
        """Covers INCR and DECR."""
        # Arrange
        counter_key = "my_counter"

        # Act & Assert (INCR)
        assert await fake_redis_client.incr(counter_key) == 1
        assert await fake_redis_client.incr(counter_key, amount=2) == 3
        assert await fake_redis_client.get(counter_key) == "3"

        # Act & Assert (DECR)
        assert await fake_redis_client.decr(counter_key) == 2
        assert await fake_redis_client.decr(counter_key, amount=2) == 0
        assert await fake_redis_client.get(counter_key) == "0"

    async def test_flushdb(self, fake_redis_client: RedisClient):
        """Covers FLUSHDB."""
        # Arrange
        await fake_redis_client.set("k1", "v1")
        await fake_redis_client.hset("h1", mapping={"f1": "v1"})

        # Act
        assert await fake_redis_client.flushdb() is True

        # Assert
        assert await fake_redis_client.exists("k1") == 0
        assert await fake_redis_client.exists("h1") == 0

    async def test_publish_and_subscribe(self, fake_redis_client: RedisClient):
        """Covers PUBLISH and SUBSCRIBE operations."""
        # Arrange
        channel = "test_channel"
        message = "test_message"

        # Act & Assert (subscribe)
        pubsub = await fake_redis_client.subscribe(channel)
        assert pubsub is not None

        # Act & Assert (publish)
        subscribers = await fake_redis_client.publish(channel, message)
        # With fakeredis, the number of subscribers might be 0 or 1 depending on implementation
        # but it should be a non-negative integer
        assert isinstance(subscribers, int)
        assert subscribers >= 0

        # Clean up
        await pubsub.aclose()

    async def test_subscribe_multiple_channels(self, fake_redis_client: RedisClient):
        """Covers SUBSCRIBE with multiple channels."""
        # Arrange
        channels = ["channel1", "channel2", "channel3"]

        # Act
        pubsub = await fake_redis_client.subscribe(*channels)

        # Assert
        assert pubsub is not None

        # Clean up
        await pubsub.aclose()

    async def test_publish_error_wrapping(self, fake_redis_client: RedisClient):
        """Covers error wrapping for PUBLISH operation."""
        # Arrange
        with patch.object(fake_redis_client.client, "publish", new_callable=AsyncMock) as mock_publish:
            mock_publish.side_effect = RedisError("Publish error")

            # Act & Assert
            with pytest.raises(RedisOperationError, match="Publish error"):
                await fake_redis_client.publish("channel", "message")

    async def test_subscribe_error_wrapping(self, fake_redis_client: RedisClient):
        """Covers error wrapping for SUBSCRIBE operation."""
        # Arrange
        with patch.object(fake_redis_client.client, "pubsub") as mock_pubsub:
            mock_pubsub.side_effect = RedisError("Subscribe error")

            # Act & Assert
            with pytest.raises(RedisOperationError, match="Subscribe error"):
                await fake_redis_client.subscribe("channel")

    @pytest.mark.parametrize(
        "method_name, args",
        [
            ("get", ("key",)),
            ("set", ("key", "value")),
            ("delete", ("key",)),
            ("exists", ("key",)),
            ("expire", ("key", 10)),
            ("ttl", ("key",)),
            ("hget", ("name", "key")),
            ("hset", ("name", {"key": "value"})),
            ("hgetall", ("name",)),
            ("hdel", ("name", "key")),
            ("lpush", ("name", "value")),
            ("rpush", ("name", "value")),
            ("lpop", ("name",)),
            ("rpop", ("name",)),
            ("llen", ("name",)),
            ("sadd", ("name", "value")),
            ("srem", ("name", "value")),
            ("smembers", ("name",)),
            ("sismember", ("name", "value")),
            ("incr", ("name",)),
            ("decr", ("name",)),
            ("ping", ()),
            ("flushdb", ()),
            ("publish", ("channel", "message")),
        ],
    )
    async def test_operation_error_wrapping(self, fake_redis_client: RedisClient, method_name, args):
        """
        Arrange: Mock the underlying client to raise a RedisError.
        Act: Call the corresponding RedisClient method.
        Assert: The RedisError is caught and wrapped in a RedisOperationError.
        """
        # This is a bit tricky with fakeredis, so we'll patch the underlying client
        # on our already-created RedisClient instance.
        with patch.object(fake_redis_client.client, method_name, new_callable=AsyncMock) as mock_method:
            mock_method.side_effect = RedisError("Underlying error")

            with pytest.raises(RedisOperationError, match="Underlying error"):
                method_to_call = getattr(fake_redis_client, method_name)
                await method_to_call(*args)


# endregion


# region Test Error Recovery Decorators and Context Managers
@pytest.mark.asyncio
class TestErrorRecovery:
    """Tests for @redis_safe decorator and redis_safe_context."""

    async def test_redis_safe_decorator_returns_default_on_error(self):
        """
        Arrange: A function decorated with @redis_safe that will raise an error.
        Act: Call the decorated function.
        Assert: The specified default value is returned.
        """
        mock_client = AsyncMock(spec=RedisClient)
        mock_client.get.side_effect = RedisOperationError("Failed")

        @redis_safe(default="fallback")
        async def get_data(client, key):
            return await client.get(key)

        result = await get_data(mock_client, "some_key")
        assert result == "fallback"

    async def test_redis_safe_decorator_returns_value_on_success(self):
        """
        Arrange: A function decorated with @redis_safe that will succeed.
        Act: Call the decorated function.
        Assert: The function's return value is returned.
        """
        mock_client = AsyncMock(spec=RedisClient)
        mock_client.get.return_value = "actual_value"

        @redis_safe(default="fallback")
        async def get_data(client, key):
            return await client.get(key)

        result = await get_data(mock_client, "some_key")
        assert result == "actual_value"

    async def test_redis_safe_context_returns_default_on_error(self):
        """
        Arrange: A client method that will raise an error.
        Act: Execute the method within the redis_safe_context.
        Assert: The specified default value is returned.
        """
        mock_client = AsyncMock(spec=RedisClient)
        mock_client.get.side_effect = RedisOperationError("Failed")

        async with redis_safe_context() as safe:
            result = await safe.execute(mock_client.get, "key", default="fallback")

        assert result == "fallback"

    async def test_redis_safe_context_returns_value_on_success(self):
        """
        Arrange: A client method that will succeed.
        Act: Execute the method within the redis_safe_context.
        Assert: The method's return value is returned.
        """
        mock_client = AsyncMock(spec=RedisClient)
        mock_client.get.return_value = "actual_value"

        async with redis_safe_context() as safe:
            result = await safe.execute(mock_client.get, "key", default="fallback")

        assert result == "actual_value"


# endregion


# region Test Health Check and Dependency
@pytest.mark.asyncio
class TestHealthAndDependency:
    """Tests for health checks and the get_redis dependency."""

    async def test_health_check_success(self, manager: RedisManager):
        """
        Arrange: A successfully connected manager.
        Act: Call check_health.
        Assert: Returns a healthy status dictionary.
        """
        await manager.setup(provider="fake")
        health = await manager.check_health()
        assert health == {
            "provider": "fake",
            "connected": True,
            "ping": True,
            "error": None,
        }

    async def test_health_check_failure(self, manager: RedisManager):
        """
        Arrange: A manager whose client will fail the ping test.
        Act: Call check_health.
        Assert: Returns an unhealthy status dictionary with the error message.
        """
        await manager.setup(provider="fake")
        with patch(
            "faster.core.redis.RedisClient.ping",
            side_effect=RedisOperationError("Ping failed"),
        ):
            health = await manager.check_health()
        assert health == {
            "provider": "fake",
            "connected": False,
            "ping": False,
            "error": "Ping failed",
        }

    async def test_get_redis_dependency(self, fake_redis_client: RedisClient):
        """
        Arrange: The global redis_mgr is initialized (via fixture).
        Act: Call the get_redis() dependency function.
        Assert: It returns the correct, initialized client instance.
        """
        client = get_redis()
        assert client is fake_redis_client
        assert isinstance(client, RedisClient)
        assert await client.ping() is True


# endregion
