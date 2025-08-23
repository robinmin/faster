import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from redis.asyncio.client import Redis
from redis.asyncio.connection import ConnectionPool
from redis.exceptions import ConnectionError

from faster.core.redis import RedisManager


@pytest.fixture
def redis_manager():
    """Provides a clean RedisManager instance for each test."""
    return RedisManager()


@pytest.fixture
def mock_connection_pool():
    """Fixture to mock redis.asyncio.ConnectionPool."""
    with patch("faster.core.redis.ConnectionPool.from_url") as mock_from_url:
        mock_pool = MagicMock(spec=ConnectionPool)
        mock_pool.disconnect = AsyncMock()
        mock_from_url.return_value = mock_pool
        yield mock_from_url, mock_pool


@pytest.fixture
def mock_redis_client():
    """
    Fixture to mock redis.asyncio.Redis client.
    We use a MagicMock for the instance and explicitly make async methods AsyncMocks.
    """
    with patch("faster.core.redis.Redis", autospec=True) as mock_redis_class:
        # Configure the class to return a new mock for each call
        def client_factory(*args, **kwargs):
            client = MagicMock(spec=Redis)
            client.ping = AsyncMock(return_value=True)
            client.close = AsyncMock()
            return client

        mock_redis_class.side_effect = client_factory
        yield mock_redis_class


class TestRedisManagerLifecycle:
    """Tests for the setup, close, and state of the RedisManager."""

    def test_initialization(self, redis_manager: RedisManager):
        """
        Arrange: A new RedisManager instance.
        Act: -
        Assert: All client and pool attributes are initially None.
        """
        assert redis_manager.master_pool is None
        assert redis_manager.replica_pool is None
        assert redis_manager.master is None
        assert redis_manager.replica is None

    @pytest.mark.asyncio
    async def test_setup_master_only_success(
        self, redis_manager: RedisManager, mock_connection_pool, mock_redis_client
    ):
        """
        Arrange: Mocks for successful master connection.
        Act: Call setup with only a master URL.
        Assert: Master pool and client are created and configured correctly.
        """
        # Arrange
        mock_pool_from_url, _ = mock_connection_pool
        master_url = "redis://master:6379"

        # Act
        await redis_manager.setup(master_url=master_url)

        # Assert
        mock_pool_from_url.assert_called_once_with(master_url, decode_responses=True, max_connections=10)
        mock_redis_client.assert_called_once_with(connection_pool=redis_manager.master_pool)
        assert redis_manager.master is not None
        redis_manager.master.ping.assert_awaited_once()

        assert redis_manager.replica is None
        assert redis_manager.master_pool is not None
        assert redis_manager.replica_pool is None

    @pytest.mark.asyncio
    async def test_setup_master_and_replica_success(
        self, redis_manager: RedisManager, mock_connection_pool, mock_redis_client
    ):
        """
        Arrange: Mocks for successful master and replica connections.
        Act: Call setup with both master and replica URLs.
        Assert: Both master and replica pools/clients are created and configured.
        """
        # Arrange
        mock_pool_from_url, _ = mock_connection_pool
        master_url = "redis://master:6379"
        replica_url = "redis://replica:6379"

        # Act
        await redis_manager.setup(master_url=master_url, replica_url=replica_url)

        # Assert
        assert mock_pool_from_url.call_count == 2
        mock_pool_from_url.assert_has_calls(
            [
                call(master_url, decode_responses=True, max_connections=10),
                call(replica_url, decode_responses=True, max_connections=10),
            ],
            any_order=True,
        )

        assert mock_redis_client.call_count == 2
        assert redis_manager.master is not None
        assert redis_manager.replica is not None
        redis_manager.master.ping.assert_awaited_once()
        redis_manager.replica.ping.assert_awaited_once()

        assert redis_manager.master_pool is not None
        assert redis_manager.replica_pool is not None

    @pytest.mark.asyncio
    async def test_setup_connection_failure(
        self, redis_manager: RedisManager, mock_connection_pool, mock_redis_client, caplog
    ):
        """
        Arrange: Mock Redis client to raise a ConnectionError on ping.
        Act: Call setup.
        Assert: An error is logged, and the setup fails gracefully (attributes are None).
        """
        # Arrange
        mock_redis_client.side_effect = [ConnectionError("Connection failed")]
        master_url = "redis://failing-master:6379"

        # Act
        await redis_manager.setup(master_url=master_url)

        # Assert
        assert "Failed to connect to Redis master" in caplog.text
        assert "Connection failed" in caplog.text
        assert redis_manager.master is None
        assert redis_manager.master_pool is None

    @pytest.mark.asyncio
    async def test_close_with_active_connections(self, redis_manager: RedisManager):
        """
        Arrange: A RedisManager with mocked active master and replica connections.
        Act: Call the close method.
        Assert: The close/disconnect methods on clients/pools are called and attributes are reset.
        """
        # Arrange
        mock_master_client = MagicMock(spec=Redis)
        mock_master_client.close = AsyncMock()
        mock_master_pool = MagicMock(spec=ConnectionPool)
        mock_master_pool.disconnect = AsyncMock()

        mock_replica_client = MagicMock(spec=Redis)
        mock_replica_client.close = AsyncMock()
        mock_replica_pool = MagicMock(spec=ConnectionPool)
        mock_replica_pool.disconnect = AsyncMock()

        redis_manager.master = mock_master_client
        redis_manager.master_pool = mock_master_pool
        redis_manager.replica = mock_replica_client
        redis_manager.replica_pool = mock_replica_pool

        # Act
        await redis_manager.close()

        # Assert
        mock_master_client.close.assert_awaited_once()
        mock_master_pool.disconnect.assert_awaited_once()
        mock_replica_client.close.assert_awaited_once()
        mock_replica_pool.disconnect.assert_awaited_once()

        assert redis_manager.master is None
        assert redis_manager.master_pool is None
        assert redis_manager.replica is None
        assert redis_manager.replica_pool is None

    @pytest.mark.asyncio
    async def test_close_without_active_connections(self, redis_manager: RedisManager):
        """
        Arrange: A RedisManager with no active connections.
        Act: Call the close method.
        Assert: The method completes without raising any exceptions.
        """
        try:
            await redis_manager.close()
        except Exception as e:
            pytest.fail(f"close() raised an unexpected exception: {e}")


class TestRedisManagerClientSelection:
    """Tests the _get_client method logic."""

    @pytest.fixture
    def configured_manager(self) -> RedisManager:
        """Provides a manager with mocked clients for testing."""
        manager = RedisManager()
        manager.master = MagicMock(spec=Redis, name="MasterClient")
        manager.replica = MagicMock(spec=Redis, name="ReplicaClient")
        return manager

    def test_get_client_readonly_uses_replica(self, configured_manager: RedisManager):
        """
        Arrange: A manager with both master and replica clients.
        Act: Get client with readonly=True.
        Assert: The replica client is returned.
        """
        client = configured_manager._get_client(readonly=True)
        assert client == configured_manager.replica

    def test_get_client_readonly_falls_back_to__master(self, configured_manager: RedisManager):
        """
        Arrange: A manager with only a master client.
        Act: Get client with readonly=True.
        Assert: The master client is returned as a fallback.
        """
        configured_manager.replica = None
        client = configured_manager._get_client(readonly=True)
        assert client == configured_manager.master

    def test_get_client_write_uses_master(self, configured_manager: RedisManager):
        """
        Arrange: A manager with both master and replica clients.
        Act: Get client with readonly=False.
        Assert: The master client is returned.
        """
        client = configured_manager._get_client(readonly=False)
        assert client == configured_manager.master

    def test_get_client_returns_none_if_no_clients(self, redis_manager: RedisManager):
        """
        Arrange: A manager with no clients configured.
        Act: Get client.
        Assert: None is returned.
        """
        client = redis_manager._get_client()
        assert client is None


class TestRedisManagerHealthCheck:
    """Tests the check_health method."""

    @pytest.mark.asyncio
    async def test_check_health_all_healthy(self, redis_manager: RedisManager):
        """
        Arrange: Manager with master and replica that return True on ping.
        Act: Call check_health.
        Assert: Returns a dict indicating both are healthy.
        """
        redis_manager.master = MagicMock(spec=Redis)
        redis_manager.master.ping = AsyncMock(return_value=True)
        redis_manager.replica = MagicMock(spec=Redis)
        redis_manager.replica.ping = AsyncMock(return_value=True)

        health = await redis_manager.check_health()
        assert health == {"master": True, "replica": True}

    @pytest.mark.asyncio
    async def test_check_health_master_unhealthy(self, redis_manager: RedisManager):
        """
        Arrange: Manager with a master that fails on ping.
        Act: Call check_health.
        Assert: Returns a dict indicating master is unhealthy.
        """
        redis_manager.master = MagicMock(spec=Redis)
        redis_manager.master.ping = AsyncMock(side_effect=asyncio.TimeoutError)
        redis_manager.replica = MagicMock(spec=Redis)
        redis_manager.replica.ping = AsyncMock(return_value=True)

        health = await redis_manager.check_health()
        assert health == {"master": False, "replica": True}

    @pytest.mark.asyncio
    async def test_check_health_no_clients(self, redis_manager: RedisManager):
        """
        Arrange: Manager with no clients.
        Act: Call check_health.
        Assert: Returns a dict indicating both are unhealthy.
        """
        health = await redis_manager.check_health()
        assert health == {"master": False, "replica": False}


class TestRedisManagerProxyMethods:
    """Tests a sample of the proxy methods to Redis commands."""

    @pytest.fixture
    def ready_manager(self) -> RedisManager:
        """Provides a manager with a mocked master client ready for use."""
        manager = RedisManager()
        manager.master = MagicMock(spec=Redis)
        return manager

    @pytest.mark.asyncio
    async def test_get_command(self, ready_manager: RedisManager):
        """
        Arrange: A manager with a mocked client's 'get' method configured.
        Act: Call the 'get' proxy method.
        Assert: The underlying client's 'get' method is called with the correct arguments.
        """
        # Arrange
        ready_manager.master.get = AsyncMock(return_value="test_value")

        # Act
        result = await ready_manager.get("test_key")

        # Assert
        ready_manager.master.get.assert_awaited_once_with("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_set_value_command(self, ready_manager: RedisManager):
        """
        Arrange: A manager with a mocked client's 'set' method configured.
        Act: Call the 'set_value' proxy method.
        Assert: The underlying client's 'set' method is called with correct arguments.
        """
        # Arrange
        ready_manager.master.set = AsyncMock(return_value=True)

        # Act
        result = await ready_manager.set_value("test_key", "test_value", expire=300)

        # Assert
        ready_manager.master.set.assert_awaited_once_with("test_key", "test_value", ex=300)
        assert result is True

    @pytest.mark.asyncio
    async def test_command_with_no_client(self, redis_manager: RedisManager):
        """
        Arrange: A manager with no client configured.
        Act: Call a proxy method ('get').
        Assert: Returns a sensible default (None) without error.
        """
        result = await redis_manager.get("any_key")
        assert result is None


class TestRedisDecorators:
    """Tests for the @cached and @locked decorators."""

    # Tests for @cached decorator would go here.
    # Requires a more complex setup with a real or fake redis.

    # Tests for @locked decorator would go here.
