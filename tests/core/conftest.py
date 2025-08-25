import asyncio

from faster.core.redis import redis_mgr


def pytest_configure(config):
    """
    Initializes the Redis manager with a fake provider before tests are collected.
    """
    asyncio.run(redis_mgr.setup(provider="fake"))
