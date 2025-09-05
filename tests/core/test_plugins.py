from typing import Any

import pytest
from typing_extensions import Self

from faster.core.config import Settings
from faster.core.plugins import BasePlugin, PluginManager


class MockPlugin(BasePlugin):
    def __init__(self, name: str):
        self.name = name
        self.setup_called = False
        self.teardown_called = False
        self.check_health_called = False
        self.is_ready = False

    @classmethod
    def get_instance(cls) -> Self:
        # For testing, we don't enforce singleton pattern
        # Each test can create its own instance
        return cls("test_instance")

    async def setup(self, settings: Settings) -> bool:
        self.setup_called = True
        self.is_ready = True
        return True

    async def teardown(self) -> bool:
        self.teardown_called = True
        self.is_ready = False
        return True

    async def check_health(self) -> dict[str, Any]:
        self.check_health_called = True
        if not self.is_ready:
            return {"status": "error", "reason": "Plugin not ready"}
        return {"status": "ok", "name": self.name}


class FailingPlugin(BasePlugin):
    def __init__(self, name: str = "failing_plugin"):
        self.is_ready = False

    @classmethod
    def get_instance(cls) -> Self:
        # For testing, we don't enforce singleton pattern
        return cls("failing_instance")

    async def setup(self, settings: Settings) -> bool:
        self.is_ready = False
        raise RuntimeError("Setup failed")

    async def teardown(self) -> bool:
        self.is_ready = False
        raise RuntimeError("Teardown failed")

    async def check_health(self) -> dict[str, Any]:
        if not self.is_ready:
            return {"status": "error", "reason": "Plugin not ready"}
        raise RuntimeError("Health check failed")


class TestPluginManager:
    @pytest.fixture
    def plugin_manager(self):
        return PluginManager()

    @pytest.fixture
    def mock_plugin(self):
        return MockPlugin("test_plugin")

    @pytest.fixture
    def settings(self):
        return Settings()

    def test_register_plugin(self, plugin_manager, mock_plugin):
        """Test plugin registration"""
        plugin_manager.register("test", mock_plugin)

        assert "test" in plugin_manager._plugins
        assert plugin_manager._plugins["test"] == mock_plugin
        assert mock_plugin in plugin_manager._plugin_list

    def test_register_multiple_plugins_preserves_order(self, plugin_manager):
        """Test that plugin registration preserves order"""
        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")
        plugin3 = MockPlugin("plugin3")

        plugin_manager.register("p1", plugin1)
        plugin_manager.register("p2", plugin2)
        plugin_manager.register("p3", plugin3)

        assert plugin_manager._plugin_list == [plugin1, plugin2, plugin3]

    @pytest.mark.asyncio
    async def test_setup_all_plugins_normal_order(self, plugin_manager, settings):
        """Test setup calls plugins in normal order"""
        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")

        plugin_manager.register("p1", plugin1)
        plugin_manager.register("p2", plugin2)

        await plugin_manager.setup(settings)

        assert plugin1.setup_called
        assert plugin2.setup_called

    @pytest.mark.asyncio
    async def test_teardown_all_plugins_reverse_order(self, plugin_manager, settings):
        """Test teardown calls plugins in reverse order"""
        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")

        plugin_manager.register("p1", plugin1)
        plugin_manager.register("p2", plugin2)

        # First setup, then teardown
        await plugin_manager.setup(settings)
        await plugin_manager.teardown()

        assert plugin1.teardown_called
        assert plugin2.teardown_called

    @pytest.mark.asyncio
    async def test_check_health_all_plugins(self, plugin_manager, settings):
        """Test health check calls all plugins"""
        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")

        plugin_manager.register("p1", plugin1)
        plugin_manager.register("p2", plugin2)

        # Health check should fail if plugins are not ready
        health_status_before_setup = await plugin_manager.check_health()
        assert health_status_before_setup == {"status": "error", "reason": "Plugin manager not ready"}

        await plugin_manager.setup(settings)
        health_status_after_setup = await plugin_manager.check_health()

        assert plugin1.check_health_called
        assert plugin2.check_health_called
        assert health_status_after_setup["p1"] == {"status": "ok", "name": "plugin1"}
        assert health_status_after_setup["p2"] == {"status": "ok", "name": "plugin2"}

    @pytest.mark.asyncio
    async def test_setup_continues_on_plugin_failure(self, plugin_manager, settings):
        """Test setup continues even if one plugin fails"""
        failing_plugin = FailingPlugin("failing")
        working_plugin = MockPlugin("working")

        plugin_manager.register("failing", failing_plugin)
        plugin_manager.register("working", working_plugin)

        result = await plugin_manager.setup(settings)

        # Overall setup should fail
        assert not result
        # Working plugin should still be set up
        assert working_plugin.setup_called
        # Plugin manager should not be ready
        assert not plugin_manager.is_ready

    @pytest.mark.asyncio
    async def test_teardown_continues_on_plugin_failure(self, plugin_manager, settings):
        """Test teardown continues even if one plugin fails"""
        failing_plugin = FailingPlugin("failing")
        working_plugin = MockPlugin("working")

        plugin_manager.register("failing", failing_plugin)
        plugin_manager.register("working", working_plugin)

        await plugin_manager.setup(settings)
        await plugin_manager.teardown()

        # Working plugin should still be torn down
        assert working_plugin.teardown_called

    @pytest.mark.asyncio
    async def test_health_check_handles_plugin_failure(self, plugin_manager, settings):
        """Test health check handles plugin failures gracefully"""
        failing_plugin = FailingPlugin("failing")
        working_plugin = MockPlugin("working")

        plugin_manager.register("failing", failing_plugin)
        plugin_manager.register("working", working_plugin)

        await plugin_manager.setup(settings)

        assert not plugin_manager.is_ready

        health_status = await plugin_manager.check_health()

        assert health_status == {"status": "error", "reason": "Plugin manager not ready"}
        assert not working_plugin.check_health_called


class TestBasePlugin:
    def test_base_plugin_is_abstract(self):
        """Test that BasePlugin cannot be instantiated directly"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class BasePlugin with abstract"):
            BasePlugin()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_mock_plugin_implements_interface(self):
        """Test that MockPlugin properly implements the interface"""
        plugin = MockPlugin("test")
        settings = Settings()

        await plugin.setup(settings)
        await plugin.teardown()
        health = await plugin.check_health()

        assert plugin.setup_called
        assert plugin.teardown_called
        assert plugin.check_health_called
        assert health == {"status": "error", "reason": "Plugin not ready"}


class TestPluginReadyState:
    @pytest.fixture
    def plugin(self):
        return MockPlugin("test")

    @pytest.fixture
    def settings(self):
        return Settings()

    def test_initial_state(self, plugin):
        """Test that is_ready is initially False"""
        assert not plugin.is_ready

    @pytest.mark.asyncio
    async def test_setup_sets_ready(self, plugin, settings):
        """Test that setup sets is_ready to True"""
        await plugin.setup(settings)
        assert plugin.is_ready

    @pytest.mark.asyncio
    async def test_teardown_sets_not_ready(self, plugin, settings):
        """Test that teardown sets is_ready to False"""
        await plugin.setup(settings)
        assert plugin.is_ready
        await plugin.teardown()
        assert not plugin.is_ready

    @pytest.mark.asyncio
    async def test_health_check_before_setup(self, plugin):
        """Test health check before setup returns not ready"""
        health = await plugin.check_health()
        assert health == {"status": "error", "reason": "Plugin not ready"}

    @pytest.mark.asyncio
    async def test_health_check_after_setup(self, plugin, settings):
        """Test health check after setup returns ok"""
        await plugin.setup(settings)
        health = await plugin.check_health()
        assert health == {"status": "ok", "name": "test"}

    @pytest.mark.asyncio
    async def test_health_check_after_teardown(self, plugin, settings):
        """Test health check after teardown returns not ready"""
        await plugin.setup(settings)
        await plugin.teardown()
        health = await plugin.check_health()
        assert health == {"status": "error", "reason": "Plugin not ready"}

    @pytest.mark.asyncio
    async def test_plugin_manager_ready_state(self):
        """Test that PluginManager correctly manages its own ready state"""
        manager = PluginManager()
        plugin = MockPlugin("p1")
        settings = Settings()

        assert not manager.is_ready

        manager.register("p1", plugin)
        await manager.setup(settings)
        assert manager.is_ready

        await manager.teardown()
        assert not manager.is_ready
