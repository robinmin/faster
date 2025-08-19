from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
import functools
import json
import logging
from typing import Any, Generic, Literal, ParamSpec, TypeVar, cast

from pydantic import BaseModel
from redis.asyncio.client import Pipeline, PubSub, Redis
from redis.asyncio.connection import ConnectionPool
from redis.asyncio.lock import Lock

logger = logging.getLogger(__name__)

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")


class RedisManager:
    """
    A Redis manager that acts as a proxy to the Redis client,
    handling the connection pool and providing wrapper methods for Redis operations.
    """

    _pool: ConnectionPool | None = None
    _client: Redis | None = None

    async def __aenter__(self) -> RedisManager:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    def _get_client(self) -> Redis:
        """
        Returns the Redis client, raising an error if not initialized.
        """
        if not self._client:
            raise ConnectionError("Redis client is not initialized.")
        return self._client

    async def initialize(
        self,
        redis_url: str,
        redis_max_connections: int = 50,
        redis_decode_responses: bool = True,
    ) -> None:
        """
        Initializes the Redis connection pool and client.
        This method should be called during application startup.
        """
        if not self._pool:
            self._pool = ConnectionPool.from_url(
                redis_url,
                max_connections=redis_max_connections,
                decode_responses=redis_decode_responses,
            )
            self._client = Redis(connection_pool=self._pool)

    async def close(self) -> None:
        """
        Closes the Redis connection pool.
        This method should be called during application shutdown.
        """
        if self._pool:
            await self._pool.disconnect()
            self._pool = None
            self._client = None

    # --- Proxy Methods for Redis Commands ---

    async def ping(self) -> bool:
        """
        Ping the Redis server.
        """
        client: Redis = self._get_client()
        return cast(bool, await client.ping())

    async def get(self, key: str) -> str | None:
        """
        Get the value of a key.
        """
        client: Redis = self._get_client()
        return cast(str | None, await client.get(key))

    async def set_value(self, key: str, value: str | bytes | int | float, expire: int | None = None) -> bool:
        """
        Set the value of a key with an optional expiration in seconds.
        """
        client: Redis = self._get_client()
        result = await client.set(key, value, ex=expire)
        return result is True

    async def delete(self, *keys: str) -> int:
        """
        Delete one or more keys.
        """
        client: Redis = self._get_client()
        return cast(int, await client.delete(*keys))

    async def exists(self, *keys: str) -> int:
        """
        Check if one or more keys exist.
        """
        client: Redis = self._get_client()
        return cast(int, await client.exists(*keys))

    async def expire(self, key: str, seconds: int) -> bool:
        """
        Set an expiration time on a key in seconds.
        """
        client: Redis = self._get_client()
        return cast(bool, await client.expire(key, seconds))

    async def ttl(self, key: str) -> int:
        """
        Get the time-to-live for a key in seconds.
        """
        client: Redis = self._get_client()
        return cast(int, await client.ttl(key))

    async def incr(self, key: str, amount: int = 1) -> int:
        """
        Increment the integer value of a key by a given amount.
        """
        client: Redis = self._get_client()
        return cast(int, await client.incr(key, amount=amount))

    async def decr(self, key: str, amount: int = 1) -> int:
        """
        Decrement the integer value of a key by a given amount.
        """
        client: Redis = self._get_client()
        return cast(int, await client.decr(key, amount=amount))

    async def hset(
        self,
        name: str,
        key: str | None = None,
        value: Any | None = None,
        mapping: dict[str, Any] | None = None,
    ) -> int:
        """
        Set a field in a hash, or multiple fields from a mapping.
        """
        client: Redis = self._get_client()
        coro = client.hset(name, key=key, value=value, mapping=mapping)
        result = await cast(Awaitable[int], coro)
        return result

    async def hget(self, name: str, key: str) -> str | None:
        """
        Get the value of a field in a hash.
        """
        client: Redis = self._get_client()
        coro = client.hget(name, key)
        result = await cast(Awaitable[str | None], coro)
        return result

    async def hgetall(self, name: str) -> dict[str, str]:
        """
        Get all fields and values in a hash.
        """
        client: Redis = self._get_client()
        coro = client.hgetall(name)
        result = await cast(Awaitable[dict[Any, Any]], coro)
        return cast(dict[str, str], result)

    async def hdel(self, name: str, *keys: str) -> int:
        """
        Delete one or more fields from a hash.
        """
        client: Redis = self._get_client()
        coro = client.hdel(name, *keys)
        result = await cast(Awaitable[int], coro)
        return result

    async def lpush(self, name: str, *values: Any) -> int:
        """
        Prepend one or more values to a list.
        """
        client: Redis = self._get_client()
        coro = client.lpush(name, *values)
        result = await cast(Awaitable[int], coro)
        return result

    async def rpush(self, name: str, *values: Any) -> int:
        """
        Append one or more values to a list.
        """
        client: Redis = self._get_client()
        coro = client.rpush(name, *values)
        result = await cast(Awaitable[int], coro)
        return result

    async def lpop(self, name: str) -> str | None:
        """
        Remove and return the first element of a list.
        """
        client: Redis = self._get_client()
        coro = client.lpop(name)
        result = await cast(Awaitable[str | list[Any] | None], coro)
        return cast(str | None, result)

    async def rpop(self, name: str) -> str | None:
        """
        Remove and return the last element of a list.
        """
        client: Redis = self._get_client()
        coro = client.rpop(name)
        result = await cast(Awaitable[str | list[Any] | None], coro)
        return cast(str | None, result)

    async def lrange(self, name: str, start: int, end: int) -> list[str]:
        """
        Get a range of elements from a list.
        """
        client: Redis = self._get_client()
        coro = client.lrange(name, start, end)
        result = await cast(Awaitable[list[Any]], coro)
        return cast(list[str], result)

    async def llen(self, name: str) -> int:
        """
        Get the length of a list.
        """
        client: Redis = self._get_client()
        coro = client.llen(name)
        result = await cast(Awaitable[int], coro)
        return result

    async def sadd(self, name: str, *values: Any) -> int:
        """
        Add one or more members to a set.
        """
        client: Redis = self._get_client()
        coro = client.sadd(name, *values)
        result = await cast(Awaitable[int], coro)
        return result

    async def srem(self, name: str, *values: Any) -> int:
        """
        Remove one or more members from a set.
        """
        client: Redis = self._get_client()
        coro = client.srem(name, *values)
        result = await cast(Awaitable[int], coro)
        return result

    async def smembers(self, name: str) -> set[str]:
        """
        Get all members of a set.
        """
        client: Redis = self._get_client()
        coro = client.smembers(name)
        result = await cast(Awaitable[set[Any]], coro)
        return cast(set[str], result)

    async def sismember(self, name: str, value: Any) -> bool:
        """
        Check if a member exists in a set.
        """
        client: Redis = self._get_client()
        coro = client.sismember(name, value)
        result = await cast(Awaitable[Literal[0, 1]], coro)
        return bool(result)

    async def acquire_lock(self, name: str, timeout: float | None = None, blocking: bool = True) -> Lock | None:
        """
        Acquire a lock and return the lock object if successful.
        """
        client: Redis = self._get_client()
        lock = client.lock(name, timeout=timeout)
        if bool(await lock.acquire(blocking=blocking)):
            return lock
        return None

    async def release_lock(self, lock: Lock) -> None:
        """
        Release a lock.
        """
        await lock.release()

    async def publish(self, channel: str, message: Any) -> int:
        """
        Publish a message to a channel.
        """
        client: Redis = self._get_client()
        return cast(int, await client.publish(channel, message))

    async def subscribe(self, *channels: str) -> PubSub | None:
        """
        Subscribe to one or more channels and return the PubSub object.
        """
        client: Redis = self._get_client()
        pubsub = client.pubsub(ignore_subscribe_messages=True)
        await pubsub.subscribe(*channels)
        return cast(PubSub | None, pubsub)

    def pipeline(self, transaction: bool = True) -> Pipeline:
        """
        Create a pipeline for executing multiple commands.
        """
        client = self._get_client()
        return client.pipeline(transaction=transaction)

    async def health_check(self) -> bool:
        """
        Perform a health check on the Redis connection.
        Returns True if the connection is healthy, False otherwise.
        """
        try:
            return await self.ping()
        except Exception as exp:
            logger.error(f"Redis health check failed: {exp}")
        return False


# Singleton instance of the RedisManager
redis_manager = RedisManager()


async def get_redis() -> AsyncGenerator[RedisManager, None]:
    """FastAPI dependency that provides an async redis_manager instance."""
    async with redis_manager:
        yield redis_manager


def cached(
    expire: int = 300,
    key_prefix: str = "cache",
    key_builder: Callable[..., str] | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    A decorator to cache the results of a function in Redis.

    Args:
        expire: Expiration time in seconds for the cached item. Defaults to 300 seconds (5 minutes).
        key_prefix: Prefix for the cache key. Defaults to "cache".
        key_builder: An optional callable to build the cache key.
                        It should accept the same arguments as the decorated function
                        and return a string.
    Returns:
        A decorator that caches the result of the function.
    Example:
        @cached(expire=600, key_prefix="my_cache")
        async def my_function(arg1, arg2):
            # Function logic here
            return result

        # Call the function with arguments
        result = await my_function(arg1, arg2)
        # The result will be cached and retrieved from Redis if the key exists.
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Generate a default cache key based on function name and arguments
                # Convert args and kwargs to a consistent string representation
                args_str = json.dumps(args, sort_keys=True, default=str)
                kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
                cache_key = f"{key_prefix}:{func.__name__}:{args_str}:{kwargs_str}"

            cached_result = await redis_manager.get(cache_key)
            if cached_result:
                logger.debug(f"Cache hit for key: {cache_key}")
                try:
                    return cast(R, json.loads(cached_result))
                except json.JSONDecodeError:
                    logger.warning(f"Failed to decode cached value for key: {cache_key}. Recomputing.")
                    # Fall through to recompute

            logger.debug(f"Cache miss for key: {cache_key}. Recomputing.")
            result = await func(*args, **kwargs)
            await redis_manager.set_value(cache_key, json.dumps(result), expire)
            return result

        return wrapper

    return decorator


def locked(
    lock_name: str | None = None,
    timeout: float | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    A decorator to acquire a distributed lock before executing the decorated function.

    Args:
        lock_name: The name of the lock. If None, the lock name will be derived from the function name.
        timeout: The maximum time in seconds to hold the lock. If None, the lock will be held indefinitely.
    Returns:
        A decorator that acquires a lock before executing the function.
    Example:
        @locked(lock_name="my_lock", timeout=10)
        async def my_function(arg1, arg2):
            # Function logic here
            return result

        # The function will only execute if the lock is acquired successfully.
        If the lock cannot be acquired, it will log a warning and proceed without the lock.
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            key = lock_name if lock_name else f"lock:{func.__name__}"
            lock = await redis_manager.acquire_lock(key, timeout=timeout)
            if not lock:
                logger.warning(f"Failed to acquire lock: {key}")
                # Depending on desired behavior, you might raise an exception here
                # or return a default value. For now, we'll proceed without the lock.
                return await func(*args, **kwargs)
            try:
                return await func(*args, **kwargs)
            finally:
                await redis_manager.release_lock(lock)

        return wrapper

    return decorator


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

    async def publish(self, channel: str, event: Event[Any]) -> int:
        """
        Publishes an event to a specified channel.
        """
        message = event.model_dump_json()
        return await self._redis_manager.publish(channel, message)

    async def subscribe(self, channel: str) -> AsyncGenerator[Event[Any], None]:
        """
        Subscribes to a channel and yields events as they are received.
        """
        pubsub = await self._redis_manager.subscribe(channel)
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
event_bus = EventBus(redis_manager)
