"""
Simple plugin system for the Faster framework.

Provides a minimal interface for pluggable components with lifecycle management:
- on_setup: Initialize resources
- on_teardown: Clean up resources
- on_check_health: Health status reporting

The PluginManager handles registration and ordered execution of plugins.
"""

from abc import ABC, abstractmethod
from typing import Any

from typing_extensions import Self

from .config import Settings
from .logger import get_logger

logger = get_logger(__name__)


class BasePlugin(ABC):
    """Abstract base class for all plugins.

    All plugins must implement the singleton pattern with a _instance class variable
    and a get_instance class method for consistent resource management.
    """

    @classmethod
    @abstractmethod
    def get_instance(cls) -> Self:
        """Get the singleton instance of this plugin.

        Returns:
            Self: The singleton instance of the current plugin class
        """

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

    _instance = None

    def __init__(self) -> None:
        self._plugins: dict[str, BasePlugin] = {}
        self._plugin_list: list[BasePlugin] = []
        self.is_ready: bool = False

    @classmethod
    def get_instance(cls) -> Self:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, name: str, plugin: BasePlugin) -> None:
        """Register a plugin with the manager."""
        self._plugins[name] = plugin
        self._plugin_list.append(plugin)
        logger.debug(f"Registered plugin: {name}")

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

    async def check_health(self) -> dict[str, Any]:
        """Check health of all plugins."""
        if not self.is_ready:
            return {"status": "error", "reason": "Plugin manager not ready"}

        health_status = {}

        for name, plugin in self._plugins.items():
            try:
                logger.debug(f"Checking health of plugin: {name}")
                health_status[name] = await plugin.check_health()
            except Exception as e:
                logger.error(f"Health check failed for plugin {name}: {e}")
                health_status[name] = {"error": str(e)}

        return health_status
