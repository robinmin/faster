"""
Redis multi-provider library with simple exception recovery mechanisms.

This module provides a unified interface for Redis operations with simple error recovery:
- Core operations always raise exceptions for explicit error handling
- Decorators and context managers for graceful error recovery
- Clean separation of concerns

Usage:
    # Basic usage (raises exceptions)
    client = await redis_manager.get_client()
    await client.set("key", "value")
    value = await client.get("key")

    # With error recovery using decorator
    @redis_safe(default="default_value")
    async def get_user_preference(client, user_id):
        return await client.get(f"user:{user_id}:preference")

    # With error recovery using context manager
    async with redis_safe_context() as safe:
        result = await safe.execute(client.get, "cache_key", default=None)
"""

from abc import ABC, abstractmethod
import builtins
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from enum import Enum
from functools import wraps
import re
from typing import Any, ParamSpec, TypeVar, cast

import fakeredis.aioredis
import redis.asyncio as redis
from redis.asyncio.client import PubSub
from redis.exceptions import RedisError
from redis.typing import FieldT
from typing_extensions import Self

from .config import Settings
from .exceptions import AppError
from .logger import get_logger
from .plugins import BasePlugin

logger = get_logger(__name__)

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")

# Legacy type aliases for backward compatibility
RedisValue = Any


class RedisProvider(str, Enum):
    """Supported Redis providers."""

    LOCAL = "local"
    UPSTASH = "upstash"
    FAKE = "fake"


class RedisConnectionError(Exception):
    """Raised when Redis connection fails."""


class RedisOperationError(Exception):
    """Raised when Redis operation fails."""


###############################################################################
# Utility decorators - Error Recovery Mechanisms
###############################################################################
def redis_safe(
    default: Any = None, log_errors: bool = True
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R | Any]]]:
    """
    Decorator for safe Redis operations that return default value on error.

    Args:
        default: Default value to return on error
        log_errors: Whether to log errors

    Usage:
        @redis_safe(default=[])
        async def get_user_tags(client, user_id):
            tags = await client.get(f"user:{user_id}:tags")
            return json.loads(tags) if tags else []
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R | Any]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | Any:
            try:
                return await func(*args, **kwargs)
            except (RedisOperationError, RedisError, Exception) as e:
                if log_errors:
                    logger.warning(f"Redis operation failed in {func.__name__}: {e}")
                return default

        return wrapper

    return decorator


class RedisSafeContext:
    """Context manager for safe Redis operations."""

    def __init__(self, log_errors: bool = True):
        self.log_errors = log_errors

    async def execute(
        self,
        operation: Callable[P, Awaitable[R]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R | Any:
        """Execute Redis operation safely with default fallback."""
        # Extract default value from kwargs if provided
        default = kwargs.pop("default", None)
        try:
            return await operation(*args, **kwargs)
        except (RedisOperationError, RedisError, Exception) as e:
            if self.log_errors:
                logger.warning(f"Redis operation failed: {e}")
            return default


@asynccontextmanager
async def redis_safe_context(
    log_errors: bool = True,
) -> AsyncIterator[RedisSafeContext]:
    """
    Context manager for safe Redis operations.

    Usage:
        async with redis_safe_context() as safe:
            result = await safe.execute(client.get, "key", default="fallback")
    """
    yield RedisSafeContext(log_errors=log_errors)


def redis_fallback(
    fallback_func: Callable[..., Awaitable[R]],
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Decorator that calls fallback function on Redis error.

    Usage:
        @redis_fallback(lambda user_id: database.get_user(user_id))
        async def get_user_from_cache(client, user_id):
            data = await client.get(f"user:{user_id}")
            return json.loads(data) if data else None
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return await func(*args, **kwargs)
            except (RedisOperationError, RedisError, Exception) as e:
                logger.warning(f"Redis operation failed in {func.__name__}, using fallback: {e}")
                # Extract non-client arguments for fallback
                fallback_args = args[1:] if args else ()
                return await fallback_func(*fallback_args, **kwargs)

        return wrapper

    return decorator


# def cached(
#     expire: int = 300,
#     key_prefix: str = "cache",
#     key_builder: Callable[..., str] | None = None,
# ) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
#     """
#     A decorator to cache the results of a function in Redis.

#     Args:
#         expire: Expiration time in seconds for the cached item. Defaults to 300 seconds (5 minutes).
#         key_prefix: Prefix for the cache key. Defaults to "cache".
#         key_builder: An optional callable to build the cache key.
#                         It should accept the same arguments as the decorated function
#                         and return a string.
#     Returns:
#         A decorator that caches the result of the function.
#     Example:
#         @cached(expire=600, key_prefix="my_cache")
#         async def my_function(arg1, arg2):
#             # Function logic here
#             return result

#         # Call the function with arguments
#         result = await my_function(arg1, arg2)
#         # The result will be cached and retrieved from Redis if the key exists.
#     """

#     def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
#         @functools.wraps(func)
#         async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
#             if key_builder:
#                 cache_key = key_builder(*args, **kwargs)
#             else:
#                 # Generate a default cache key based on function name and arguments
#                 # Convert args and kwargs to a consistent string representation
#                 args_str = json.dumps(args, sort_keys=True, default=str)
#                 kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
#                 cache_key = f"{key_prefix}:{func.__name__}:{args_str}:{kwargs_str}"

#             cached_result = await redis_mgr.get(cache_key)
#             if cached_result:
#                 logger.debug(f"Cache hit for key: {cache_key}")
#                 try:
#                     return cast(R, json.loads(cached_result))
#                 except json.JSONDecodeError:
#                     logger.warning(f"Failed to decode cached value for key: {cache_key}. Recomputing.")

#             logger.debug(f"Cache miss for key: {cache_key}. Recomputing.")
#             result = await func(*args, **kwargs)
#             await redis_mgr.set_value(cache_key, json.dumps(result, default=str), expire)
#             return result

#         return wrapper

#     return decorator


# def locked(
#     lock_name: str | None = None,
#     timeout: float | None = None,
# ) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
#     """
#     A decorator to acquire a distributed lock before executing the decorated function.

#     Args:
#         lock_name: The name of the lock. If None, the lock name will be derived from the function name.
#         timeout: The maximum time in seconds to hold the lock. If None, the lock will be held indefinitely.
#     Returns:
#         A decorator that acquires a lock before executing the function.
#     Example:
#         @locked(lock_name="my_lock", timeout=10)
#         async def my_function(arg1, arg2):
#             # Function logic here
#             return result

#         # The function will only execute if the lock is acquired successfully.
#         If the lock cannot be acquired, it will log a warning and proceed without the lock.
#     """

#     def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
#         @functools.wraps(func)
#         async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
#             key = lock_name if lock_name else f"lock:{func.__name__}"
#             lock = await redis_mgr.acquire_lock(key, timeout=timeout)
#             if not lock:
#                 logger.warning(f"Failed to acquire lock: {key}")
#                 # Depending on desired behavior, you might raise an exception here
#                 # or return a default value. For now, we'll proceed without the lock.
#                 return await func(*args, **kwargs)
#             try:
#                 return await func(*args, **kwargs)
#             finally:
#                 await redis_mgr.release_lock(lock)

#         return wrapper

#     return decorator


###############################################################################
# Core Redis Interface and Implementation
###############################################################################
class RedisInterface(ABC):
    """Abstract interface for Redis operations."""

    @abstractmethod
    async def get(self, key: str) -> Any:
        """Get value by key."""

    @abstractmethod
    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """Set key-value with optional expiration and conditions."""

    @abstractmethod
    async def delete(self, *keys: str) -> int:
        """Delete one or more keys."""

    @abstractmethod
    async def exists(self, *keys: str) -> int:
        """Check if keys exist."""

    @abstractmethod
    async def expire(self, key: str, time: int) -> bool:
        """Set expiration time for key."""

    @abstractmethod
    async def ttl(self, key: str) -> int:
        """Get time to live for key."""

    @abstractmethod
    async def hget(self, name: str, key: str) -> str | None:
        """Get hash field value."""

    @abstractmethod
    async def hset(self, name: str, mapping: dict[str, Any]) -> int:
        """Set hash fields."""

    @abstractmethod
    async def hgetall(self, name: str) -> dict[str, Any]:
        """Get all hash fields and values."""

    @abstractmethod
    async def hdel(self, name: str, *keys: str) -> int:
        """Delete hash fields."""

    @abstractmethod
    async def lpush(self, name: str, *values: str) -> int:
        """Push values to list head."""

    @abstractmethod
    async def rpush(self, name: str, *values: str) -> int:
        """Push values to list tail."""

    @abstractmethod
    async def lpop(self, name: str) -> str | list[Any] | None:
        """Pop value from list head."""

    @abstractmethod
    async def rpop(self, name: str) -> str | list[Any] | None:
        """Pop value from list tail."""

    @abstractmethod
    async def llen(self, name: str) -> int:
        """Get list length."""

    @abstractmethod
    async def sadd(self, name: str, *values: FieldT) -> int:
        """Add members to set."""

    @abstractmethod
    async def srem(self, name: str, *values: str) -> int:
        """Remove members from set."""

    @abstractmethod
    async def smembers(self, name: str) -> builtins.set[Any]:
        """Get all set members."""

    @abstractmethod
    async def sismember(self, name: str, value: str) -> bool:
        """Check if value is set member."""

    @abstractmethod
    async def incr(self, name: str, amount: int = 1) -> int:
        """Increment key value."""

    @abstractmethod
    async def decr(self, name: str, amount: int = 1) -> int:
        """Decrement key value."""

    @abstractmethod
    async def ping(self) -> bool:
        """Test connection."""

    @abstractmethod
    async def flushdb(self) -> bool:
        """Clear current database."""

    @abstractmethod
    async def publish(self, channel: str, message: str) -> int:
        """Publish message to channel."""

    @abstractmethod
    async def subscribe(self, *channels: str) -> PubSub:
        """Subscribe to channel."""


###############################################################################


class RedisClient(RedisInterface):
    """Redis client wrapper implementing the RedisInterface."""

    def __init__(self, client: redis.Redis | fakeredis.aioredis.FakeRedis):
        self.client = client
        self._is_fake = isinstance(client, fakeredis.aioredis.FakeRedis)

    async def get(self, key: str) -> Any:
        try:
            result = await self.client.get(key)
            if isinstance(result, Awaitable):
                actual_result = await result  # pyright: ignore[reportUnknownVariableType]
            else:
                actual_result = result
            return cast(Any, actual_result)  # pyright: ignore[reportUnknownVariableType]
        except (RedisError, Exception) as e:
            logger.error(f"Redis GET operation failed for key '{key}': {e}")
            raise RedisOperationError(f"GET operation failed: {e}") from e

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        try:
            result = await self.client.set(key, value, ex=ex, nx=nx, xx=xx)
            # For nx=True or xx=True, Redis returns None when condition is not met
            # We should preserve this behavior
            if (nx or xx) and result is None:
                return False
            return bool(result)
        except (RedisError, Exception) as e:
            logger.error(f"Redis SET operation failed for key '{key}': {e}")
            raise RedisOperationError(f"SET operation failed: {e}") from e

    async def delete(self, *keys: str) -> int:
        try:
            if not keys:
                return 0
            return int(await self.client.delete(*keys))
        except (RedisError, Exception) as e:
            logger.error(f"Redis DELETE operation failed for keys {keys}: {e}")
            raise RedisOperationError(f"DELETE operation failed: {e}") from e

    async def exists(self, *keys: str) -> int:
        try:
            if not keys:
                return 0
            return int(await self.client.exists(*keys))
        except (RedisError, Exception) as e:
            logger.error(f"Redis EXISTS operation failed for keys {keys}: {e}")
            raise RedisOperationError(f"EXISTS operation failed: {e}") from e

    async def expire(self, key: str, time: int) -> bool:
        try:
            return bool(await self.client.expire(key, time))
        except (RedisError, Exception) as e:
            logger.error(f"Redis EXPIRE operation failed for key '{key}': {e}")
            raise RedisOperationError(f"EXPIRE operation failed: {e}") from e

    async def ttl(self, key: str) -> int:
        try:
            return int(await self.client.ttl(key))
        except (RedisError, Exception) as e:
            logger.error(f"Redis TTL operation failed for key '{key}': {e}")
            raise RedisOperationError(f"TTL operation failed: {e}") from e

    async def hget(self, name: str, key: str) -> str | None:
        try:
            result = self.client.hget(name, key)
            return await result if isinstance(result, Awaitable) else result
        except (RedisError, Exception) as e:
            logger.error(f"Redis HGET operation failed for hash '{name}', key '{key}': {e}")
            raise RedisOperationError(f"HGET operation failed: {e}") from e

    async def hset(self, name: str, mapping: dict[str, Any]) -> int:
        try:
            if not mapping:
                return 0
            result = self.client.hset(name, mapping=mapping)
            return await result if isinstance(result, Awaitable) else result
        except (RedisError, Exception) as e:
            logger.error(f"Redis HSET operation failed for hash '{name}': {e}")
            raise RedisOperationError(f"HSET operation failed: {e}") from e

    async def hgetall(self, name: str) -> dict[str, Any]:
        try:
            result = self.client.hgetall(name)  # pyright: ignore[reportUnknownVariableType]
            if isinstance(result, Awaitable):
                actual_result = await result  # pyright: ignore[reportUnknownVariableType]
            else:
                actual_result = result  # pyright: ignore[reportUnknownVariableType]
            return cast(dict[str, Any], actual_result)  # pyright: ignore[reportUnknownVariableType]
        except (RedisError, Exception) as e:
            logger.error(f"Redis HGETALL operation failed for hash '{name}': {e}")
            raise RedisOperationError(f"HGETALL operation failed: {e}") from e

    async def hdel(self, name: str, *keys: str) -> int:
        try:
            if not keys:
                return 0
            result = self.client.hdel(name, *keys)
            return await result if isinstance(result, Awaitable) else result
        except (RedisError, Exception) as e:
            logger.error(f"Redis HDEL operation failed for hash '{name}', keys {keys}: {e}")
            raise RedisOperationError(f"HDEL operation failed: {e}") from e

    async def lpush(self, name: str, *values: str) -> int:
        try:
            if not values:
                return 0
            result = self.client.lpush(name, *values)
            return await result if isinstance(result, Awaitable) else result
        except (RedisError, Exception) as e:
            logger.error(f"Redis LPUSH operation failed for list '{name}': {e}")
            raise RedisOperationError(f"LPUSH operation failed: {e}") from e

    async def rpush(self, name: str, *values: str) -> int:
        try:
            if not values:
                return 0
            result = self.client.rpush(name, *values)
            return await result if isinstance(result, Awaitable) else result
        except (RedisError, Exception) as e:
            logger.error(f"Redis RPUSH operation failed for list '{name}': {e}")
            raise RedisOperationError(f"RPUSH operation failed: {e}") from e

    async def lpop(self, name: str) -> str | list[Any] | None:
        try:
            result = self.client.lpop(name)  # pyright: ignore[reportUnknownVariableType]
            if isinstance(result, Awaitable):
                actual_result = await result  # pyright: ignore[reportUnknownVariableType]
            else:
                actual_result = result  # pyright: ignore[reportUnknownVariableType]
            return actual_result  # pyright: ignore[reportUnknownVariableType]
        except (RedisError, Exception) as e:
            logger.error(f"Redis LPOP operation failed for list '{name}': {e}")
            raise RedisOperationError(f"LPOP operation failed: {e}") from e

    async def rpop(self, name: str) -> str | list[Any] | None:
        try:
            result = self.client.rpop(name)  # pyright: ignore[reportUnknownVariableType]
            if isinstance(result, Awaitable):
                actual_result = await result  # pyright: ignore[reportUnknownVariableType]
            else:
                actual_result = result  # pyright: ignore[reportUnknownVariableType]
            return actual_result  # pyright: ignore[reportUnknownVariableType]
        except (RedisError, Exception) as e:
            logger.error(f"Redis RPOP operation failed for list '{name}': {e}")
            raise RedisOperationError(f"RPOP operation failed: {e}") from e

    async def llen(self, name: str) -> int:
        try:
            result = self.client.llen(name)
            return await result if isinstance(result, Awaitable) else result
        except (RedisError, Exception) as e:
            logger.error(f"Redis LLEN operation failed for list '{name}': {e}")
            raise RedisOperationError(f"LLEN operation failed: {e}") from e

    async def sadd(self, name: str, *values: FieldT) -> int:
        try:
            if not values:
                return 0
            result = self.client.sadd(name, *values)
            return await result if isinstance(result, Awaitable) else result
        except (RedisError, Exception) as e:
            logger.error(f"Redis SADD operation failed for set '{name}': {e}")
            raise RedisOperationError(f"SADD operation failed: {e}") from e

    async def srem(self, name: str, *values: str) -> int:
        try:
            if not values:
                return 0
            result = self.client.srem(name, *values)
            return await result if isinstance(result, Awaitable) else result
        except (RedisError, Exception) as e:
            logger.error(f"Redis SREM operation failed for set '{name}': {e}")
            raise RedisOperationError(f"SREM operation failed: {e}") from e

    async def smembers(self, name: str) -> builtins.set[Any]:
        try:
            result = self.client.smembers(name)  # pyright: ignore[reportUnknownVariableType]
            if isinstance(result, Awaitable):
                actual_result = await result  # pyright: ignore[reportUnknownVariableType]
            else:
                actual_result = result  # pyright: ignore[reportUnknownVariableType]
            return actual_result  # pyright: ignore[reportUnknownVariableType]
        except (RedisError, Exception) as e:
            logger.error(f"Redis SMEMBERS operation failed for set '{name}': {e}")
            raise RedisOperationError(f"SMEMBERS operation failed: {e}") from e

    async def sismember(self, name: str, value: str) -> bool:
        try:
            result = self.client.sismember(name, value)
            return bool(await result if isinstance(result, Awaitable) else result)
        except (RedisError, Exception) as e:
            logger.error(f"Redis SISMEMBER operation failed for set '{name}', value '{value}': {e}")
            raise RedisOperationError(f"SISMEMBER operation failed: {e}") from e

    async def incr(self, name: str, amount: int = 1) -> int:
        try:
            return int(await self.client.incr(name, amount))
        except (RedisError, Exception) as e:
            logger.error(f"Redis INCR operation failed for key '{name}': {e}")
            raise RedisOperationError(f"INCR operation failed: {e}") from e

    async def decr(self, name: str, amount: int = 1) -> int:
        try:
            return int(await self.client.decr(name, amount))
        except (RedisError, Exception) as e:
            logger.error(f"Redis DECR operation failed for key '{name}': {e}")
            raise RedisOperationError(f"DECR operation failed: {e}") from e

    async def ping(self) -> bool:
        try:
            result = await self.client.ping()
            return result is True or result in [b"PONG", "PONG"]
        except (RedisError, Exception) as e:
            logger.error(f"Redis PING operation failed: {e}")
            raise RedisOperationError(f"PING operation failed: {e}") from e

    async def flushdb(self) -> bool:
        try:
            await self.client.flushdb()
            return True
        except (RedisError, Exception) as e:
            logger.error(f"Redis FLUSHDB operation failed: {e}")
            raise RedisOperationError(f"FLUSHDB operation failed: {e}") from e

    async def close(self) -> None:
        """Close the Redis connection."""
        try:
            if hasattr(self.client, "close") and not self._is_fake:
                await self.client.close()
                logger.debug("Redis connection closed")
        except Exception as e:
            logger.warning(f"Error closing Redis connection: {e}")

    async def publish(self, channel: str, message: str) -> int:
        """
        Publish a message to a channel.

        Args:
            channel: The channel name
            message: The message to publish

        Returns:
            Number of subscribers that received the message
        """
        try:
            result = await self.client.publish(channel, message)
            logger.debug(f"Published message to channel '{channel}', reached {result} subscribers")
            return int(result)
        except (RedisError, Exception) as e:
            logger.error(f"Redis PUBLISH operation failed for channel '{channel}': {e}")
            raise RedisOperationError(f"PUBLISH operation failed: {e}") from e

    async def subscribe(self, *channels: str) -> PubSub:
        """
        Subscribe to channels and return a pub/sub object.

        Args:
            *channels: Channel names to subscribe to

        Returns:
            RedisPubSub: Pub/sub object for managing subscriptions and receiving messages

        Example:
            pubsub = await client.subscribe("notifications", "alerts")
            async for message in pubsub.listen():
                print(f"Received: {message}")
            await pubsub.close()
        """
        try:
            pubsub = self.client.pubsub()
            await pubsub.subscribe(*channels)
            logger.debug(f"Created subscription to channels: {channels}")
            return pubsub
        except (RedisError, Exception) as e:
            logger.error(f"Redis SUBSCRIBE operation failed for channels {channels}: {e}")
            raise RedisOperationError(f"SUBSCRIBE operation failed: {e}") from e


###############################################################################


class RedisManager(BasePlugin):
    """Manages Redis connections for different providers."""

    _instance = None

    def __init__(self) -> None:
        self._client: RedisClient | None = None
        self._provider: RedisProvider | None = None
        self.is_ready: bool = False

    @classmethod
    def get_instance(cls) -> Self:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def _setup_internal(  # noqa: C901
        self,
        provider: str | RedisProvider = RedisProvider.LOCAL,
        redis_url: str | None = None,
        # Connection parameters (only used when redis_url is not provided for local)
        host: str = "localhost",
        port: int = 6379,
        password: str | None = None,
        db: int = 0,
        # Additional connection parameters
        socket_connect_timeout: int = 5,
        socket_timeout: int = 5,
        max_connections: int | None = None,
        decode_responses: bool = True,
        fallback_to_fake: bool = True,
        **kwargs: Any,
    ) -> None:
        """
        Initialize Redis client with specified provider and parameters.

        Args:
            provider: Redis provider type ('local', 'upstash', or 'fake')
            redis_url: Redis connection URL (e.g., 'redis://localhost:6379/0' or Upstash URL)
                      If not provided for local provider, will construct from host/port/password/db
            host: Redis server host (used only if redis_url not provided for local)
            port: Redis server port (used only if redis_url not provided for local)
            password: Redis password (used only if redis_url not provided for local)
            db: Redis database number (used only if redis_url not provided for local)
            socket_connect_timeout: Connection timeout in seconds
            socket_timeout: Socket timeout in seconds
            max_connections: Maximum number of connections in connection pool
            decode_responses: Whether to decode responses to strings
            fallback_to_fake: Whether to fallback to fake Redis on connection failure
            **kwargs: Additional connection parameters (ssl_cert_reqs, ssl_ca_certs, etc.)

        Examples:
            # Local Redis with URL
            await manager.setup(provider="local", redis_url="redis://localhost:6379/0")

            # Local Redis with individual parameters
            await manager.setup(provider="local", host="localhost", port=6379, db=0)

            # Upstash Redis
            await manager.setup(provider="upstash", redis_url="redis://upstash-url:port")

            # Fake Redis for testing
            await manager.setup(provider="fake")

        Raises:
            RedisConnectionError: If connection fails and fallback is disabled
            ValueError: If invalid provider or missing required parameters
        """
        if isinstance(provider, str):
            try:
                provider = RedisProvider(provider.lower())
            except ValueError as exp:
                raise ValueError(f"Invalid provider '{provider}'. Must be one of: {list(RedisProvider)}") from exp

        self._provider = provider

        try:
            if provider == RedisProvider.UPSTASH:
                if not redis_url:
                    raise ValueError("redis_url is required for upstash provider")
                await self._setup_from_url(
                    url=redis_url,
                    socket_connect_timeout=socket_connect_timeout,
                    socket_timeout=socket_timeout,
                    decode_responses=decode_responses,
                    **kwargs,
                )
            elif provider == RedisProvider.FAKE:
                await self._setup_fake(decode_responses=decode_responses)
            elif redis_url:
                await self._setup_from_url(
                    url=redis_url,
                    socket_connect_timeout=socket_connect_timeout,
                    socket_timeout=socket_timeout,
                    max_connections=max_connections,
                    decode_responses=decode_responses,
                    **kwargs,
                )
            else:
                await self._setup_local(
                    host=host,
                    port=port,
                    password=password,
                    db=db,
                    socket_connect_timeout=socket_connect_timeout,
                    socket_timeout=socket_timeout,
                    max_connections=max_connections,
                    decode_responses=decode_responses,
                    **kwargs,
                )
            # Test connection
            if self._client:
                _ = await self._client.ping()
                logger.info(f"Successfully connected to Redis provider: {provider.value}")
            self.is_ready = True
        except Exception as e:
            self.is_ready = False
            logger.error(f"Failed to connect to Redis provider '{provider.value}': {e}")

            if fallback_to_fake and provider != RedisProvider.FAKE:
                logger.warning("Falling back to fake Redis for development/testing")
                try:
                    await self._setup_fake(decode_responses=decode_responses)
                    self._provider = RedisProvider.FAKE
                    logger.info("Successfully initialized fake Redis fallback")
                    self.is_ready = True
                except Exception as fallback_error:
                    logger.error(f"Fallback to fake Redis failed: {fallback_error}")
                    raise RedisConnectionError(f"Redis connection failed and fallback failed: {fallback_error}") from e
            else:
                raise RedisConnectionError(f"Redis connection failed: {e}") from e

    async def _setup_from_url(self, url: str, max_connections: int | None = None, **kwargs: Any) -> None:
        """Initialize Redis connection from URL (works for both local and Upstash)."""
        if not url:
            raise ValueError("redis_url is required")

        if max_connections:
            # Create connection pool for better performance
            pool = redis.ConnectionPool.from_url(url, max_connections=max_connections, **kwargs)
            redis_client = redis.Redis(connection_pool=pool)
        else:
            redis_client = redis.Redis.from_url(url, **kwargs)

        self._client = RedisClient(redis_client)
        logger.debug(f"Initialized Redis client from URL: {self._mask_url(url)}")

    async def _setup_local(self, **kwargs: Any) -> None:
        """Initialize local Redis connection from individual parameters."""
        max_connections = kwargs.pop("max_connections", None)

        if max_connections:
            pool = redis.ConnectionPool(max_connections=max_connections, **kwargs)
            redis_client = redis.Redis(connection_pool=pool)
        else:
            redis_client = redis.Redis(**kwargs)

        self._client = RedisClient(redis_client)
        logger.debug(f"Initialized local Redis client: {kwargs.get('host', 'localhost')}:{kwargs.get('port', 6379)}")

    def _mask_url(self, url: str) -> str:
        """Mask sensitive information in URL for logging."""
        # Mask password in URL for logging: redis://user:password@host:port -> redis://user:***@host:port
        return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url)

    async def _setup_fake(self, decode_responses: bool) -> None:
        """Initialize fake Redis connection for testing."""
        redis_client = fakeredis.aioredis.FakeRedis(decode_responses=decode_responses)
        self._client = RedisClient(redis_client)
        logger.debug("Initialized fake Redis client")

    def get_client(self) -> RedisClient:
        """Get the Redis client instance."""
        if not self._client:
            raise AppError("Redis client not initialized. Call setup() first.")
        return self._client

    @property
    def provider(self) -> RedisProvider | None:
        """Get the current Redis provider."""
        return self._provider

    @property
    def is_connected(self) -> bool:
        """Check if Redis client is initialized."""
        return self._client is not None

    # -----------------------------
    # Plugin interface implementation
    # -----------------------------
    async def setup(self, settings: Settings) -> bool:
        """Initialize Redis client from settings."""
        if not settings.redis_enabled:
            logger.info("Redis not enabled, skipping Redis setup")
            self.is_ready = True
            return True

        try:
            # Convert settings to parameters for _setup_internal
            await self._setup_internal(
                provider=settings.redis_provider,
                redis_url=settings.redis_url,
                password=settings.redis_password,
                max_connections=settings.redis_max_connections,
                decode_responses=settings.redis_decode_responses,
                fallback_to_fake=settings.is_debug,  # Use debug mode to determine fallback
            )
            return self.is_ready
        except Exception as e:
            logger.error(f"Redis setup failed: {e}")
            self.is_ready = False
            return False

    async def teardown(self) -> bool:
        """Close the Redis connection."""
        if self._client:
            try:
                if self._client.client:
                    await self._client.close()
                    logger.info("Redis connection closed successfully")
                return True
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
                return False
            finally:
                self._client = None
                self._provider = None
                self.is_ready = False
        return True

    async def check_health(self) -> dict[str, Any]:
        """Perform a health check on the Redis connection."""
        if not self.is_ready:
            return {
                "provider": None,
                "connected": False,
                "ping": False,
                "reason": "Plugin not ready",
            }

        if not self._client:
            return {
                "provider": None,
                "connected": False,
                "ping": False,
                "error": "Redis client not initialized",
            }

        try:
            ping_result = await self._client.ping()
            return {
                "provider": self._provider.value if self._provider else None,
                "connected": True,
                "ping": ping_result,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "provider": self._provider.value if self._provider else None,
                "connected": False,
                "ping": False,
                "error": str(e),
            }


###############################################################################
## Use RedisManager.get_instance() to access the singleton
###############################################################################


def get_redis() -> RedisClient:
    """
    FastAPI dependency function to get Redis client instance.

    This function is designed to be used with FastAPI's Depends() for dependency injection.

    Returns:
        RedisClient: The Redis client instance

    Raises:
        AppError: If Redis manager singleton is not initialized

    Usage:
        from fastapi import Depends
        from redis import get_redis, RedisClient

        @app.get("/cache/{key}")
        async def get_cache_item(key: str, redis: RedisClient = Depends(get_redis)):
            try:
                value = await redis.get(key)
                return {"key": key, "value": value}
            except RedisOperationError:
                raise HTTPException(status_code=500, detail="Cache unavailable")

        # Or with error recovery
        @redis_safe(default=None)
        async def get_cached_data(redis: RedisClient, cache_key: str):
            return await redis.get(cache_key)

        @app.get("/data/{id}")
        async def get_data(id: str, redis: RedisClient = Depends(get_redis)):
            cached = await get_cached_data(redis, f"data:{id}")
            if cached:
                return {"data": cached, "from_cache": True}
            # Fetch from database...
            return {"data": "from_db", "from_cache": False}
    """
    return RedisManager.get_instance().get_client()
