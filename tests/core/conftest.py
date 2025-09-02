import asyncio

from faster.core.config import Settings
from faster.core.redis import RedisManager


def pytest_configure(config):
    """
    Initializes the Redis manager with a fake provider before tests are collected.
    """
    settings = Settings(redis_provider="fake")
    asyncio.run(RedisManager.get_instance().setup(settings))
