from collections.abc import Awaitable, Callable
import functools
import json
import logging
from typing import Any, ParamSpec, TypeVar, cast

# import redis.asyncio as redis
from redis.asyncio.client import Pipeline, PubSub, Redis
from redis.asyncio.connection import ConnectionPool
from redis.asyncio.lock import Lock
from redis.exceptions import ConnectionError

logger = logging.getLogger(__name__)

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")


class RedisManager:
    def __init__(self) -> None:
        self.master_pool: ConnectionPool | None = None
        self.replica_pool: ConnectionPool | None = None
        self.master: Redis | None = None
        self.replica: Redis | None = None

    async def setup(
        self,
        master_url: str,
        replica_url: str | None = None,
        decode_responses: bool = True,
        max_connections: int = 10,
    ) -> None:
        """
        Initialize Redis connection pools and clients.
        If connection fails, log error and continue without raising.
        """
        # Master pool connection
        try:
            self.master_pool = ConnectionPool.from_url(
                master_url,
                decode_responses=decode_responses,
                max_connections=max_connections,
            )
            self.master = Redis(connection_pool=self.master_pool)
            await self.master.ping()
            logger.info("Redis master connected", extra={"url": master_url})
        except ConnectionError as e:
            logger.error(f"Failed to connect to Redis master at {master_url}: {e}")
            self.master_pool = None
            self.master = None
        except Exception as e:
            logger.exception(f"Unexpected error while connecting to Redis master: {e}")
            self.master_pool = None
            self.master = None

        # Replica pool connection (optional)
        if replica_url:
            self.replica = None  # Ensure replica is None initially
            try:
                self.replica_pool = ConnectionPool.from_url(
                    replica_url,
                    decode_responses=decode_responses,
                    max_connections=max_connections,
                )
                self.replica = Redis(connection_pool=self.replica_pool)
                await self.replica.ping()
                logger.info("Redis replica connected", extra={"url": replica_url})
            except ConnectionError as e:
                logger.error(f"Failed to connect to Redis replica at {replica_url}: {e}")
                self.replica_pool = None
                self.replica = None
            except Exception as e:
                logger.exception(f"Unexpected error while connecting to Redis replica: {e}")
                self.replica_pool = None
                self.replica = None

    async def close(self) -> None:
        """Close Redis clients and their pools."""
        try:
            if self.master:
                await self.master.close()
                logger.info("Redis master client closed")
                self.master = None
            if self.master_pool:
                await self.master_pool.disconnect()
                logger.info("Redis master pool closed")
                self.master_pool = None
        except Exception:
            logger.exception("Error closing master Redis connections/pools")

        try:
            if self.replica:
                await self.replica.close()
                logger.info("Redis replica client closed")
                self.replica = None
            if self.replica_pool:
                await self.replica_pool.disconnect()
                logger.info("Redis replica pool closed")
                self.replica_pool = None
        except Exception:
            logger.exception("Error closing replica Redis connections/pools")

    async def check_health(self) -> dict[str, bool]:
        """
        Ping master and replica to check connectivity.
        Returns a dict: {"master": True/False, "replica": True/False}
        """
        results = {"master": False, "replica": False}

        try:
            if self.master:
                pong = await self.master.ping()
                results["master"] = pong is True
            else:
                logger.debug("Redis master not initialized")
        except Exception:
            logger.exception("Redis master health check failed")

        try:
            if self.replica:
                pong = await self.replica.ping()
                results["replica"] = pong is True
            else:
                logger.debug("Redis replica not initialized")
        except Exception:
            logger.exception("Redis replica health check failed")

        return results

    def _get_client(self, readonly: bool = False) -> Redis | None:
        """
        Get the appropriate Redis client.
        - readonly=True uses replica if available
        """
        if readonly and self.replica:
            return self.replica
        if self.master:
            return self.master
        return None

    #########################################################################
    # Proxy Methods for Redis Commands
    #########################################################################

    async def ping(self) -> bool:
        """
        Ping the Redis server.
        """
        client = self._get_client()
        return cast(bool, await client.ping()) if client else False

    async def get(self, key: str) -> str | None:
        """
        Get the value of a key.
        """
        client = self._get_client()
        return cast(str | None, await client.get(key)) if client else None

    async def set_value(self, key: str, value: str | bytes | int | float, expire: int | None = None) -> bool:
        """
        Set the value of a key with an optional expiration in seconds.
        """
        client = self._get_client()
        if not client:
            return False
        result = await client.set(key, value, ex=expire)
        return result is True

    async def delete(self, *keys: str) -> int:
        """
        Delete one or more keys.
        """
        client = self._get_client()
        return cast(int, await client.delete(*keys)) if client else 0

    async def exists(self, *keys: str) -> int:
        """
        Check if one or more keys exist.
        """
        client = self._get_client()
        return cast(int, await client.exists(*keys)) if client else 0

    async def expire(self, key: str, seconds: int) -> bool:
        """
        Set an expiration time on a key in seconds.
        """
        client = self._get_client()
        return cast(bool, await client.expire(key, seconds)) if client else False

    async def ttl(self, key: str) -> int:
        """
        Get the time-to-live for a key in seconds.
        """
        client = self._get_client()
        return cast(int, await client.ttl(key)) if client else 0

    async def incr(self, key: str, amount: int = 1) -> int:
        """
        Increment the integer value of a key by a given amount.
        """
        client = self._get_client()
        return cast(int, await client.incr(key, amount=amount)) if client else 0

    async def decr(self, key: str, amount: int = 1) -> int:
        """
        Decrement the integer value of a key by a given amount.
        """
        client = self._get_client()
        return cast(int, await client.decr(key, amount=amount)) if client else 0

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
        client = self._get_client()
        if not client:
            return 0
        return await client.hset(name, key=key, value=value, mapping=mapping)

    async def hget(self, name: str, key: str) -> str | None:
        """
        Get the value of a field in a hash.
        """
        client = self._get_client()
        if not client:
            return None
        return cast(str | None, await client.hget(name, key))

    async def hgetall(self, name: str) -> dict[str, str]:
        """
        Get all fields and values in a hash.
        """
        client = self._get_client()
        if not client:
            return {}
        return cast(dict[str, str], await client.hgetall(name))

    async def hdel(self, name: str, *keys: str) -> int:
        """
        Delete one or more fields from a hash.
        """
        client = self._get_client()
        if not client:
            return 0
        return await client.hdel(name, *keys)

    async def lpush(self, name: str, *values: Any) -> int:
        """
        Prepend one or more values to a list.
        """
        client = self._get_client()
        if not client:
            return 0
        return await client.lpush(name, *values)

    async def rpush(self, name: str, *values: Any) -> int:
        """
        Append one or more values to a list.
        """
        client = self._get_client()
        if not client:
            return 0
        return await client.rpush(name, *values)

    async def lpop(self, name: str) -> str | None:
        """
        Remove and return the first element of a list.
        """
        client = self._get_client()
        if not client:
            return None
        return cast(str | None, await client.lpop(name))

    async def rpop(self, name: str) -> str | None:
        """
        Remove and return the last element of a list.
        """
        client = self._get_client()
        if not client:
            return None
        return cast(str | None, await client.rpop(name))

    async def lrange(self, name: str, start: int, end: int) -> list[str]:
        """
        Get a range of elements from a list.
        """
        client = self._get_client()
        if not client:
            return []
        return cast(list[str], await client.lrange(name, start, end))

    async def llen(self, name: str) -> int:
        """
        Get the length of a list.
        """
        client = self._get_client()
        if not client:
            return 0
        return await client.llen(name)

    async def sadd(self, name: str, *values: Any) -> int:
        """
        Add one or more members to a set.
        """
        client = self._get_client()
        if not client:
            return 0
        return await client.sadd(name, *values)

    async def srem(self, name: str, *values: Any) -> int:
        """
        Remove one or more members from a set.
        """
        client = self._get_client()
        if not client:
            return 0
        return await client.srem(name, *values)

    async def smembers(self, name: str) -> set[str]:
        """
        Get all members of a set.
        """
        client = self._get_client()
        if not client:
            return set()
        return cast(set[str], await client.smembers(name))

    async def sismember(self, name: str, value: Any) -> bool:
        """
        Check if a member exists in a set.
        """
        client = self._get_client()
        if not client:
            return False
        result = await client.sismember(name, value)
        return bool(result)

    async def acquire_lock(self, name: str, timeout: float | None = None, blocking: bool = True) -> Lock | None:
        """
        Acquire a lock and return the lock object if successful.
        """
        client = self._get_client()
        if not client:
            return None
        lock: Lock = client.lock(name, timeout=timeout)
        if await lock.acquire(blocking=blocking):
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
        client = self._get_client()
        return cast(int, await client.publish(channel, message)) if client else 0

    async def subscribe(self, *channels: str) -> PubSub | None:
        """
        Subscribe to one or more channels and return the PubSub object.
        """
        client = self._get_client()
        if not client:
            return None
        pubsub = client.pubsub(ignore_subscribe_messages=True)
        await pubsub.subscribe(*channels)
        return cast(PubSub | None, pubsub)

    def pipeline(self, transaction: bool = True) -> Pipeline | None:
        """
        Create a pipeline for executing multiple commands.
        """
        client = self._get_client()
        return client.pipeline(transaction=transaction) if client else None


# singleton instance of RedisManager
redis_mgr = RedisManager()


###############################################################
# Utility decorators
###############################################################
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

            cached_result = await redis_mgr.get(cache_key)
            if cached_result:
                logger.debug(f"Cache hit for key: {cache_key}")
                try:
                    return cast(R, json.loads(cached_result))
                except json.JSONDecodeError:
                    logger.warning(f"Failed to decode cached value for key: {cache_key}. Recomputing.")

            logger.debug(f"Cache miss for key: {cache_key}. Recomputing.")
            result = await func(*args, **kwargs)
            await redis_mgr.set_value(cache_key, json.dumps(result, default=str), expire)
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
            lock = await redis_mgr.acquire_lock(key, timeout=timeout)
            if not lock:
                logger.warning(f"Failed to acquire lock: {key}")
                # Depending on desired behavior, you might raise an exception here
                # or return a default value. For now, we'll proceed without the lock.
                return await func(*args, **kwargs)
            try:
                return await func(*args, **kwargs)
            finally:
                await redis_mgr.release_lock(lock)

        return wrapper

    return decorator


###############################################################
# Utility functions for redis operations
###############################################################
async def blacklist_add(item: str, expire: int | None = None) -> bool:
    """
    Add an item to the blacklist.
    """
    return await redis_mgr.set_value(f"blacklist:{item}", "1", expire)


async def blacklist_exists(item: str) -> bool:
    """
    Check if an item is blacklisted.
    """
    result = await redis_mgr.exists(f"blacklist:{item}")
    return result > 0


async def blacklist_delete(item: str) -> bool:
    """
    Remove an item from the blacklist.
    """
    result = await redis_mgr.delete(f"blacklist:{item}")
    return result > 0


async def userinfo_get(user_id: str) -> str | None:
    """
    Get user information from the database.
    """
    return await redis_mgr.get(f"user:{user_id}")


async def userinfo_set(user_id: str, user_data: str, expire: int = 300) -> bool:
    """
    Set user information in the database.
    """
    return await redis_mgr.set_value(f"user:{user_id}", user_data, expire)


async def user2role_get(user_id: str) -> list[str]:
    """
    Get user role from the database.
    """
    roles = await redis_mgr.smembers(f"user:{user_id}:role")
    return list(roles)


async def user2role_set(user_id: str, roles: list[str] | None = None) -> bool:
    """
    Set user role in the database.
    """
    key = f"user:{user_id}:role"
    if roles is None:
        result = await redis_mgr.delete(key)
        return result > 0

    result = await redis_mgr.sadd(key, *roles)
    return result == len(roles)


async def tag2role_get(tag: str) -> list[str]:
    """
    Get tag role from the database.
    """
    roles = await redis_mgr.smembers(f"tag:{tag}:role")
    return list(roles)


async def tag2role_set(tag: str, roles: list[str] | None = None) -> bool:
    """
    Set tag role in the database.
    """
    key = f"tag:{tag}:role"
    if roles is None:
        result = await redis_mgr.delete(key)
        return result > 0

    result = await redis_mgr.sadd(key, *roles)
    return result == len(roles)
