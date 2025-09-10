from enum import Enum
import json
from typing import Any, cast

from .logger import get_logger
from .redis import get_redis

logger = get_logger(__name__)


###############################################################################
# Utility functions for redis operations
###############################################################################

CACHE_DURATION = 3600


# class KeyPrefix(StrEnum): # available in Python 3.11+
class KeyPrefix(Enum):
    """
    Centralized place to define keys for Redis operations.
    """

    BLACKLIST_TOKEN = "blacklist:token"
    USER_INFO = "user:info"
    USER_ROLES = "user:roles"
    USER_PROFILE = "user:profile"
    TAG_ROLES = "tag:roles"
    SYS_DICT = "sys:dict"
    SYS_MAP = "sys:map"
    JWKS_KEY = "jwks:key"

    def __str__(self) -> str:  # no need in Python 3.11+
        return self.value

    def get_key(self, suffix: str) -> str:
        return f"{self.value}:{suffix}"


###############################################################################


async def blacklist_add(item: str, expire: int = CACHE_DURATION) -> bool:
    """
    Add an item to the blacklist.
    """
    try:
        key = str(KeyPrefix.BLACKLIST_TOKEN)
        if not await get_redis().sadd(key, item):
            return False
        return await get_redis().expire(key, expire)
    except Exception as e:
        logger.error(f"Failed to add item to blacklist: {e}")
    return False


async def blacklist_exists(item: str) -> bool:
    """
    Check if an item is blacklisted.
    """
    try:
        return await get_redis().sismember(str(KeyPrefix.BLACKLIST_TOKEN), item)
    except Exception as e:
        logger.error(f"Failed to check item in blacklist: {e}")
    return False


async def blacklist_delete(item: str) -> bool:
    """
    Remove an item from the blacklist.
    """
    try:
        return await get_redis().srem(str(KeyPrefix.BLACKLIST_TOKEN), item) > 0
    except Exception as e:
        logger.error(f"Failed to remove item from blacklist: {e}")
    return False


###############################################################################


async def userinfo_get(user_id: str) -> str | None:
    """
    Get user information from the database.
    """
    return str(await get_redis().get(KeyPrefix.USER_INFO.get_key(user_id)))


async def userinfo_set(user_id: str, user_data: str, expire: int = 300) -> bool:
    """
    Set user information in the database.
    """
    return bool(await get_redis().set(KeyPrefix.USER_INFO.get_key(user_id), user_data, expire))


###############################################################################


async def user2role_get(user_id: str, default: list[str] | None = None) -> list[str]:
    """
    Get user role from the database.
    """
    if default is None:
        default = []
    try:
        roles = await get_redis().smembers(KeyPrefix.USER_ROLES.get_key(user_id))
        return list(roles)
    except Exception as e:
        logger.error(f"Failed to get user role: {e}")
    return default


async def user2role_set(user_id: str, roles: list[str] | None = None) -> bool:
    """
    Set user role in the database.
    """
    try:
        key = KeyPrefix.USER_ROLES.get_key(user_id)
        result = await get_redis().delete(key)

        if roles:
            result = await get_redis().sadd(key, *roles)
            return result == len(roles)
        return True
    except Exception as e:
        logger.error(f"Failed to set user role: {e}")
    return False


###############################################################################


async def tag2role_get(tag: str) -> list[str]:
    """
    Get tag role from the database.
    """
    roles = await get_redis().smembers(KeyPrefix.TAG_ROLES.get_key(tag))
    return list(roles)


async def tag2role_set(tag: str, roles: list[str] | None = None) -> bool:
    """
    Set tag role in the database.
    """
    if roles is None:
        result = await get_redis().delete(KeyPrefix.TAG_ROLES.get_key(tag))
        return result > 0

    result = await get_redis().sadd(KeyPrefix.TAG_ROLES.get_key(tag), *roles)
    return result == len(roles)


###############################################################################
async def sysdict_get(category: str, key: str) -> int | None:
    """
    Get system dictionary value from the database.
    """
    value = await get_redis().hget(KeyPrefix.SYS_DICT.get_key(category), key)
    return int(value) if value else None


async def sysdict_set(category: str, mapping: dict[int, Any]) -> bool:
    """
    Set system dictionary value from the database.
    """
    # convert items to list of tuples
    new_items = {}
    for k, v in mapping.items():
        new_items[str(k)] = v

    key = KeyPrefix.SYS_DICT.get_key(category)
    try:
        # no matter existing or not, just overwrite it
        _ = await get_redis().hset(key, new_items)
        return True
    except Exception as e:
        logger.error(f"Error when hset to [{key}] : {e}")
    return False


###############################################################################
async def sysmap_get(category: str, left: str) -> str | None:
    """
    Get system map value from the database.
    """
    return await get_redis().hget(KeyPrefix.SYS_MAP.get_key(category), left)


async def sysmap_set(category: str, mapping: dict[str, Any]) -> bool:
    """
    Set system map value from the database.
    """
    key = KeyPrefix.SYS_MAP.get_key(category)
    try:
        # no matter existing or not, just overwrite it
        _ = await get_redis().hset(key, mapping)
        return True
    except Exception as e:
        logger.error(f"Error when hset to [{key}] : {e}")
    return False


# =============================================================================
# Utility Functions  for Auth Module
# =============================================================================
async def set_user_profile(user_id: str, profile_json: str, ttl: int = 3600) -> bool:
    """Cache user profile data as JSON string."""
    # TODO: store user profile data in JSON format is not a good way to do it, use a more efficient data structure
    try:
        return bool(await get_redis().set(KeyPrefix.USER_PROFILE.get_key(user_id), profile_json, ttl))
    except Exception as e:
        logger.error(f"Error when set user profile to [{user_id}] : {e}")
    return False


async def get_user_profile(user_id: str) -> str | None:
    """Retrieve cached user profile data as JSON string."""
    # TODO: store user profile data in JSON format is not a good way to do it, use a more efficient data structure

    try:
        result = await get_redis().get(KeyPrefix.USER_PROFILE.get_key(user_id))
        return cast(str | None, result)
    except Exception as e:
        logger.error(f"Error when get user profile from [{user_id}] : {e}")
    return None


###############################################################################


async def set_jwks_key(key_id: str, key_data: dict[str, Any], ttl: int = 3600) -> bool:
    """Cache JWKS key data."""
    try:
        return bool(await get_redis().set(KeyPrefix.JWKS_KEY.get_key(key_id), json.dumps(key_data), ttl))
    except Exception as e:
        logger.error(f"Error when setting JWKS key [{key_id}] : {e}")
    return False


async def get_jwks_key(key_id: str, default: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Retrieve cached JWKS key data."""
    try:
        data = await get_redis().get(KeyPrefix.JWKS_KEY.get_key(key_id))
        if data:
            return dict(json.loads(data))
    except Exception as e:
        logger.error(f"Error when getting JWKS key [{key_id}] : {e}")
    return default
