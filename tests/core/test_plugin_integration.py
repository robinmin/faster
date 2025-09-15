"""
Integration tests for existing managers implementing the plugin interface.
"""

import pytest

from faster.core.config import Settings
from faster.core.database import DatabaseManager
from faster.core.plugins import BasePlugin, PluginManager
from faster.core.redis import RedisManager
from faster.core.sentry import SentryManager


class TestPluginInterfaceIntegration:
    """Test that existing managers properly implement the plugin interface."""

    def test_database_manager_implements_plugin_interface(self) -> None:
        """Test that DatabaseManager implements BasePlugin interface."""
        db_mgr = DatabaseManager.get_instance()
        assert isinstance(db_mgr, BasePlugin)
        assert hasattr(db_mgr, "setup")
        assert hasattr(db_mgr, "teardown")
        assert hasattr(db_mgr, "check_health")

    def test_redis_manager_implements_plugin_interface(self) -> None:
        """Test that RedisManager implements BasePlugin interface."""
        redis_mgr = RedisManager.get_instance()
        assert isinstance(redis_mgr, BasePlugin)
        assert hasattr(redis_mgr, "setup")
        assert hasattr(redis_mgr, "teardown")
        assert hasattr(redis_mgr, "check_health")

    def test_sentry_manager_implements_plugin_interface(self) -> None:
        """Test that SentryManager implements BasePlugin interface."""
        sentry_mgr = SentryManager.get_instance()
        assert isinstance(sentry_mgr, BasePlugin)
        assert hasattr(sentry_mgr, "setup")
        assert hasattr(sentry_mgr, "teardown")
        assert hasattr(sentry_mgr, "check_health")

    @pytest.mark.asyncio
    async def test_plugin_manager_can_register_existing_managers(self) -> None:
        """Test that PluginManager can register and manage existing managers."""
        plugin_manager = PluginManager.get_instance()
        sentry_mgr = SentryManager.get_instance()

        # Register existing managers
        db_mgr = DatabaseManager.get_instance()
        redis_mgr = RedisManager.get_instance()
        plugin_manager.register("database", db_mgr)
        plugin_manager.register("redis", redis_mgr)
        plugin_manager.register("sentry", sentry_mgr)

        # Verify registration
        registered_plugins = plugin_manager.get_registered_plugins()
        # AuthService may be pre-registered depending on test execution context
        expected_count = 4 if "auth" in registered_plugins else 3
        assert len(registered_plugins) == expected_count
        assert "database" in registered_plugins
        assert "redis" in registered_plugins
        assert "sentry" in registered_plugins

    @pytest.mark.asyncio
    async def test_plugin_teardown_calls_existing_manager_methods(self) -> None:
        """Test that plugin teardown properly calls existing manager close methods."""
        plugin_manager = PluginManager.get_instance()
        sentry_mgr = SentryManager.get_instance()

        # Register managers
        db_mgr = DatabaseManager.get_instance()
        redis_mgr = RedisManager.get_instance()
        plugin_manager.register("database", db_mgr)
        plugin_manager.register("redis", redis_mgr)
        plugin_manager.register("sentry", sentry_mgr)

        # Setup before teardown (minimal setup for testing)
        settings = Settings(redis_provider="fake")
        _ = await redis_mgr.setup(settings)

        # This should not raise an exception
        _ = await plugin_manager.teardown()

    @pytest.mark.asyncio
    async def test_plugin_health_check_works_with_existing_managers(self) -> None:
        """Test that plugin health check works with existing managers."""
        plugin_manager = PluginManager.get_instance()
        sentry_mgr = SentryManager.get_instance()
        settings = Settings()

        # Register managers
        db_mgr = DatabaseManager.get_instance()
        redis_mgr = RedisManager.get_instance()
        plugin_manager.register("database", db_mgr)
        plugin_manager.register("redis", redis_mgr)
        plugin_manager.register("sentry", sentry_mgr)

        # Setup Redis for health check to work
        redis_settings = Settings(redis_provider="fake")
        _ = await redis_mgr.setup(redis_settings)

        # Setup the plugin manager
        _ = await plugin_manager.setup(settings)

        # Get health status
        health_status = await plugin_manager.check_health()

        # Should have health info for all plugins
        assert "database" in health_status
        assert "redis" in health_status
        assert "sentry" in health_status

        # Redis should be healthy (fake provider)
        assert "ping" in health_status["redis"]

        # Sentry should have status info
        assert "status" in health_status["sentry"]
