from .redis import get_redis

###############################################################################
# Utility functions for redis operations
###############################################################################


async def blacklist_add(item: str, expire: int | None = None) -> bool:
    """
    Add an item to the blacklist.
    """
    return bool(await get_redis().set(f"blacklist:{item}", "1", expire))


async def blacklist_exists(item: str) -> bool:
    """
    Check if an item is blacklisted.
    """
    result = await get_redis().exists(f"blacklist:{item}")
    return result > 0


async def blacklist_delete(item: str) -> bool:
    """
    Remove an item from the blacklist.
    """
    result = await get_redis().delete(f"blacklist:{item}")
    return result > 0


async def userinfo_get(user_id: str) -> str | None:
    """
    Get user information from the database.
    """
    return str(await get_redis().get(f"user:{user_id}"))


async def userinfo_set(user_id: str, user_data: str, expire: int = 300) -> bool:
    """
    Set user information in the database.
    """
    return bool(await get_redis().set(f"user:{user_id}", user_data, expire))


async def user2role_get(user_id: str) -> list[str]:
    """
    Get user role from the database.
    """
    roles = await get_redis().smembers(f"user:{user_id}:role")
    return list(roles)


async def user2role_set(user_id: str, roles: list[str] | None = None) -> bool:
    """
    Set user role in the database.
    """
    key = f"user:{user_id}:role"
    if roles is None:
        result = await get_redis().delete(key)
        return result > 0

    result = await get_redis().sadd(key, *roles)
    return result == len(roles)


async def tag2role_get(tag: str) -> list[str]:
    """
    Get tag role from the database.
    """
    roles = await get_redis().smembers(f"tag:{tag}:role")
    return list(roles)


async def tag2role_set(tag: str, roles: list[str] | None = None) -> bool:
    """
    Set tag role in the database.
    """
    key = f"tag:{tag}:role"
    if roles is None:
        result = await get_redis().delete(key)
        return result > 0

    result = await get_redis().sadd(key, *roles)
    return result == len(roles)
