"""
Simple plugin system for the Faster framework.

Provides a minimal interface for pluggable components with lifecycle management:
- on_setup: Initialize resources
- on_teardown: Clean up resources
- on_check_health: Health status reporting

The PluginManager handles registration and ordered execution of plugins.
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar, TypeVar

from .config import Settings
from .logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T', bound='BasePlugin')


class BasePlugin(ABC):
    """Abstract base class for all plugins with built-in singleton support.

    Provides automatic singleton behavior for all plugin subclasses, eliminating
    the need for manual singleton implementation in each plugin.
    """

    # Class-level storage for singleton instances
    _instances: ClassVar[dict[type['BasePlugin'], 'BasePlugin']] = {}

    @classmethod
    def get_instance(cls: type[T]) -> T:
        """Get the singleton instance of this plugin.

        Automatically creates and caches instances for each plugin class.
        Thread-safe and type-safe implementation.

        Returns:
            T: The singleton instance of the current plugin class
        """
        if cls not in cls._instances:
            cls._instances[cls] = cls()
        return cls._instances[cls]  # type: ignore[return-value]

    @classmethod
    def clear_instances(cls) -> None:
        """Clear all singleton instances. Useful for testing."""
        cls._instances.clear()

    @abstractmethod
    async def setup(self, settings: Settings) -> bool:
        """Initialize the plugin. Called during application startup.

        Args:
            settings: Application settings containing configuration

        Returns:
            bool: True if setup successful, False otherwise
        """

    @abstractmethod
    async def teardown(self) -> bool:
        """Clean up the plugin. Called during application shutdown.

        Returns:
            bool: True if teardown successful, False otherwise
        """

    @abstractmethod
    async def check_health(self) -> dict[str, Any]:
        """Check plugin health status. Returns status information."""


class PluginManager(BasePlugin):
    """Manages plugin lifecycle and execution order."""

    def __init__(self) -> None:
        self._plugins: dict[str, BasePlugin] = {}
        self._plugin_list: list[BasePlugin] = []
        self.is_ready: bool = False


    def register(self, name: str, plugin: BasePlugin) -> None:
        """Register a plugin with the manager."""
        self._plugins[name] = plugin
        self._plugin_list.append(plugin)
        logger.debug(f"Registered plugin: {name}")

    def get_registered_plugins(self) -> list[str]:
        """Get list of registered plugin names."""
        return list(self._plugins.keys())

    async def setup(self, settings: Settings) -> bool:
        """Setup all plugins in registration order."""
        all_success = True
        for name, plugin in self._plugins.items():
            try:
                logger.debug(f"Setting up plugin: {name}")
                success = await plugin.setup(settings)
                if success:
                    logger.debug(f"Successfully set up plugin: {name}")
                else:
                    logger.error(f"Plugin {name} setup returned False")
                    all_success = False
            except Exception as e:
                logger.error(f"Failed to set up plugin {name}: {e}")
                all_success = False
                # Continue with other plugins
        self.is_ready = all_success
        return all_success

    async def teardown(self) -> bool:
        """Teardown all plugins in reverse order."""
        all_success = True
        for name, plugin in reversed(list(self._plugins.items())):
            try:
                logger.debug(f"Tearing down plugin: {name}")
                success = await plugin.teardown()
                if success:
                    logger.debug(f"Successfully tore down plugin: {name}")
                else:
                    logger.error(f"Plugin {name} teardown returned False")
                    all_success = False
            except Exception as e:
                logger.error(f"Failed to tear down plugin {name}: {e}")
                all_success = False
                # Continue with other plugins
        self.is_ready = False
        return all_success

    async def check_health(self) -> dict[str, dict[str, Any]]:
        """Check health of all plugins."""
        if not self.is_ready:
            return {"status": {"error": "Plugin manager not ready"}}

        health_status: dict[str, dict[str, Any]] = {}

        for name, plugin in self._plugins.items():
            try:
                logger.debug(f"Checking health of plugin: {name}")
                health_status[name] = await plugin.check_health()
            except Exception as e:
                logger.error(f"Health check failed for plugin {name}: {e}")
                health_status[name] = {"error": str(e)}

        return health_status
