from collections.abc import Callable
from functools import lru_cache

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.routing import Match

from ..logger import get_logger
from ..redisex import (
    MapCategory,
    sysmap_get,
)
from .models import RouterItem

logger = get_logger(__name__)


class RouterInfo:
    """
    RouterInfo class handles all router-related functionality for dynamic RBAC.

    This class is responsible for:
    - Collecting router information from FastAPI applications
    - Creating and managing route finders for fast route matching
    - Managing tag-role mappings and caching
    - Providing role-based access control functionality

    Extracted from AuthService to improve separation of concerns and maintainability.
    """

    def __init__(self) -> None:
        """Initialize RouterInfo with empty caches."""
        # Route finding and caching - key format: "METHOD path_template"
        self._route_cache: dict[str, RouterItem] = {}
        self._route_finder: Callable[[str, str], str | None] | None = None

        # Tag-role mapping cache for RBAC
        self._tag_role_cache: dict[str, list[str]] = {}

    async def refresh_data(self, app: FastAPI, is_debug: bool = False) -> list[RouterItem]:
        """
        Refresh router data from FastAPI app and compute allowed roles for each route.
        Fetches tag-role mapping internally to reduce external dependencies.

        Args:
            app: FastAPI application instance
            is_debug: Enable debug logging for router information

        Returns:
            List of RouterItem objects with computed allowed roles
        """
        router_items: list[RouterItem] = []
        self._route_cache.clear()

        # Fetch tag-role mapping internally to reduce external dependencies
        try:
            all_tag_data = await sysmap_get(str(MapCategory.TAG_ROLE))
            if all_tag_data:
                self._tag_role_cache = all_tag_data
                logger.debug(f"Refreshed tag-role cache with {len(all_tag_data)} entries")
            else:
                self._tag_role_cache = {}
                logger.debug("No tag-role mapping data found, using empty cache")
        except Exception as e:
            logger.warning(f"Failed to fetch tag-role mapping: {e}, using existing cache")

        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue

            tags = route.tags or []

            # Compute allowed roles for this route using cached tag-role mapping
            allowed_roles: set[str] = set()
            for tag in tags:
                tag_str = str(tag)  # Convert tag to string for dict lookup
                if tag_str in self._tag_role_cache:
                    tag_roles = self._tag_role_cache[tag_str]
                    if isinstance(tag_roles, list):
                        allowed_roles.update(str(role) for role in tag_roles)
                    else:
                        allowed_roles.add(str(tag_roles))

            for method in route.methods:
                router_item: RouterItem = {
                    "method": str(method),
                    "path": route.path,
                    "path_template": route.path,
                    "name": route.name or "",
                    "tags": [str(tag) for tag in tags],  # Convert tags to strings
                    "allowed_roles": allowed_roles,
                }

                # Cache using "METHOD path_template" as key
                cache_key = f"{method!s} {route.path}"
                self._route_cache[cache_key] = router_item
                router_items.append(router_item)

        # Log router information if debug mode is enabled
        if is_debug:
            self._log_router_info(router_items)

        return router_items

    def create_route_finder(self, app: FastAPI) -> Callable[[str, str], str | None]:
        """
        Create a cached route finder function for fast route matching.
        Returns cache keys for RouterItem lookup, leveraging both LRU cache and dict performance.

        Args:
            app: FastAPI application instance

        Returns:
            Route finder function that takes method and path, returns cache key or None
        """

        @lru_cache(maxsize=4096)
        def _find_route(method: str, path: str) -> str | None:
            scope = {"type": "http", "method": method, "path": path, "root_path": getattr(app, "root_path", "")}
            for route in app.routes:
                try:
                    match, _child_scope = route.matches(scope)
                except Exception:
                    continue
                if match is Match.FULL:
                    # Return cache key for RouterItem lookup
                    route_path = getattr(route, "path", path)
                    cache_key = f"{method} {route_path}"
                    return cache_key
            return None

        self._route_finder = _find_route
        return _find_route

    def find_route(self, method: str, path: str) -> RouterItem | None:
        """
        Find route information for given method and path using cached finder.
        Leverages both LRU cache for route matching and dict cache for RouterItem lookup.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path

        Returns:
            RouterItem or None if not found
        """
        if not self._route_finder:
            logger.error("Route finder not initialized. Call create_route_finder first.")
            return None

        # Get cache key from LRU-cached route finder
        cache_key = self._route_finder(method, path)
        if not cache_key:
            return None

        # Lookup RouterItem from dict cache using the key
        return self._route_cache.get(cache_key)

    def _log_router_info(self, router_items: list[RouterItem]) -> None:
        """
        Log router information for debugging purposes.

        Args:
            router_items: List of RouterItem objects
        """
        logger.debug("=========================================================")
        logger.debug("All available URLs:")
        for item in router_items:
            roles_str = ", ".join(sorted(item["allowed_roles"])) if item["allowed_roles"] else "none"
            logger.debug(
                f"  [{item['method']}] {item['path']} - {item['name']} \t# tags: {', '.join(item['tags'])}, roles: {roles_str}"
            )
        logger.debug("=========================================================")

    async def check_access(self, user_roles: set[str], allowed_roles: set[str]) -> bool:
        """Check if user has access to a given list of tags."""
        # If endpoint has required roles, ensure intersection exists
        if allowed_roles:
            if user_roles.isdisjoint(allowed_roles):
                logger.info(f"[RBAC] - denied access(0) : {user_roles} / {allowed_roles}")
                return False
            return True

        logger.info(f"[RBAC] - denied access(1) : {user_roles} / {allowed_roles}")
        return False  # no required roles → deny access

    def get_router_item(self, method: str, path_template: str) -> RouterItem | None:
        """
        Get RouterItem by method and path template.

        Args:
            method: HTTP method (GET, POST, etc.)
            path_template: Route path template

        Returns:
            RouterItem if found, None otherwise
        """
        cache_key = f"{method} {path_template}"
        return self._route_cache.get(cache_key)

    def reset_cache(self) -> None:
        """Reset all caches (tag-role, route cache, and route finder)."""
        self._tag_role_cache.clear()
        self._route_cache.clear()
        self._route_finder = None
        logger.debug("Reset all caches (tag-role, route, and route finder)")

    def get_cache_info(self) -> dict[str, int]:
        """Get information about the cache sizes."""
        return {
            "tag_role_cache_size": len(self._tag_role_cache),
            "route_cache_size": len(self._route_cache),
        }

    def get_route_cache_size(self) -> int:
        """Get the current size of the route cache."""
        return len(self._route_cache)

    def get_tag_role_cache_size(self) -> int:
        """Get the current size of the tag-role cache."""
        return len(self._tag_role_cache)
