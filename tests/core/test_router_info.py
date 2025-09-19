"""
Unit tests for RouterInfo class.
Tests the router information management and RBAC functionality.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from faster.core.auth.models import RouterItem
from faster.core.auth.router_info import RouterInfo


class TestRouterInfoInitialization:
    """Test RouterInfo initialization and basic functionality."""

    def test_init(self) -> None:
        """Test RouterInfo initialization."""
        router_info = RouterInfo()

        assert router_info._route_cache == {}  # type: ignore[reportPrivateUsage, unused-ignore]
        assert router_info._route_finder is None  # type: ignore[reportPrivateUsage, unused-ignore]
        assert router_info._tag_role_cache == {}  # type: ignore[reportPrivateUsage, unused-ignore]


class TestRouterInfoRefreshData:
    """Test RouterInfo refresh_data functionality."""

    @pytest.mark.asyncio
    async def test_refresh_data_basic(self) -> None:
        """Test basic refresh_data functionality."""
        router_info = RouterInfo()

        # Create mock FastAPI app
        mock_app = MagicMock()
        mock_route = MagicMock()
        mock_route.path = "/api/test"
        mock_route.methods = frozenset(["GET", "POST"])
        mock_route.tags = ["protected"]
        mock_route.name = "test_endpoint"

        # Mock the endpoint function
        mock_endpoint = MagicMock()
        mock_endpoint.__name__ = "test_function"
        mock_route.endpoint = mock_endpoint

        mock_app.routes = [mock_route]

        # Mock sysmap_get to return empty mapping
        with (
            patch("faster.core.auth.router_info.isinstance", return_value=True),
            patch("faster.core.auth.router_info.sysmap_get", new_callable=AsyncMock, return_value={}),
        ):
            router_items = await router_info.refresh_data(mock_app)

        assert len(router_items) == 2  # GET and POST

        # Check first item (GET)
        get_item = router_items[0]
        assert get_item["method"] in ["GET", "POST"]
        assert get_item["path"] == "/api/test"
        assert get_item["path_template"] == "/api/test"
        assert get_item["name"] == "test_endpoint"
        assert get_item["tags"] == ["protected"]
        assert get_item["allowed_roles"] == set()  # No tag-role mapping set

    @pytest.mark.asyncio
    async def test_refresh_data_with_tag_role_mapping(self) -> None:
        """Test refresh_data with tag-role mapping."""
        router_info = RouterInfo()

        # Mock sysmap_get to return tag-role mapping
        tag_role_mapping = {"protected": ["admin", "user"], "admin": ["admin"]}

        # Create mock FastAPI app
        mock_app = MagicMock()
        mock_route = MagicMock()
        mock_route.path = "/api/admin"
        mock_route.methods = frozenset(["GET"])
        mock_route.tags = ["protected", "admin"]
        mock_route.name = "admin_endpoint"

        mock_endpoint = MagicMock()
        mock_endpoint.__name__ = "admin_function"
        mock_route.endpoint = mock_endpoint

        mock_app.routes = [mock_route]

        with (
            patch("faster.core.auth.router_info.isinstance", return_value=True),
            patch("faster.core.auth.router_info.sysmap_get", new_callable=AsyncMock, return_value=tag_role_mapping),
        ):
            router_items = await router_info.refresh_data(mock_app)

        assert len(router_items) == 1

        item = router_items[0]
        assert item["method"] == "GET"
        assert item["tags"] == ["protected", "admin"]
        # Should have roles from both tags, deduplicated (now as set)
        assert item["allowed_roles"] == {"admin", "user"}

    @pytest.mark.asyncio
    async def test_refresh_data_with_debug_logging(self) -> None:
        """Test refresh_data with debug logging enabled."""
        router_info = RouterInfo()

        mock_app = MagicMock()
        mock_route = MagicMock()
        mock_route.path = "/api/test"
        mock_route.methods = frozenset(["GET"])
        mock_route.tags = ["test"]
        mock_route.name = "test_endpoint"

        mock_endpoint = MagicMock()
        mock_endpoint.__name__ = "test_function"
        mock_route.endpoint = mock_endpoint

        mock_app.routes = [mock_route]

        with (
            patch("faster.core.auth.router_info.isinstance", return_value=True),
            patch("faster.core.auth.router_info.sysmap_get", new_callable=AsyncMock, return_value={}),
            patch("faster.core.auth.router_info.logger") as mock_logger,
        ):
            _ = await router_info.refresh_data(mock_app, is_debug=True)

            # Should have called debug logging
            assert mock_logger.debug.called
            debug_calls = [call.args[0] for call in mock_logger.debug.call_args_list]
            assert any("All available URLs:" in call for call in debug_calls)

    @pytest.mark.asyncio
    async def test_refresh_data_clears_cache(self) -> None:
        """Test that refresh_data clears existing cache."""
        router_info = RouterInfo()

        # Add some existing cache data
        router_info._route_cache["OLD /old"] = {  # type: ignore[reportPrivateUsage, unused-ignore]
            "method": "GET",
            "path": "/old",
            "path_template": "/old",
            "name": "old",
            "tags": [],
            "allowed_roles": set(),
        }

        # Create new mock app
        mock_app = MagicMock()
        mock_app.routes = []  # Empty routes

        with patch("faster.core.auth.router_info.sysmap_get", new_callable=AsyncMock, return_value={}):
            router_items = await router_info.refresh_data(mock_app)

        assert len(router_items) == 0


class TestRouterInfoRouteFinding:
    """Test RouterInfo route finding functionality."""

    def test_create_route_finder(self) -> None:
        """Test creating route finder."""
        router_info = RouterInfo()
        mock_app = MagicMock()

        route_finder = router_info.create_route_finder(mock_app)

        assert route_finder is not None
        assert router_info._route_finder is not None  # type: ignore[reportPrivateUsage, unused-ignore]
        assert router_info._route_finder == route_finder  # type: ignore[reportPrivateUsage, unused-ignore]

    def test_find_route_success(self) -> None:
        """Test successful route finding."""
        router_info = RouterInfo()

        # Mock route finder to return cache key
        cache_key = "GET /api/test"
        mock_finder = MagicMock(return_value=cache_key)
        router_info._route_finder = mock_finder  # type: ignore[reportPrivateUsage, unused-ignore]

        # Add RouterItem to cache
        mock_router_item: RouterItem = {
            "method": "GET",
            "path": "/api/test",
            "path_template": "/api/test",
            "name": "test",
            "tags": ["protected"],
            "allowed_roles": set(),
        }
        router_info._route_cache[cache_key] = mock_router_item  # type: ignore[reportPrivateUsage, unused-ignore]

        result = router_info.find_route("GET", "/api/test")

        assert result == mock_router_item
        mock_finder.assert_called_once_with("GET", "/api/test")

    def test_find_route_no_finder(self) -> None:
        """Test route finding when no finder is set."""
        router_info = RouterInfo()

        with patch("faster.core.auth.router_info.logger") as mock_logger:
            result = router_info.find_route("GET", "/api/test")

            assert result is None
            mock_logger.error.assert_called_once_with("Route finder not initialized. Call create_route_finder first.")


class TestRouterInfoTagRoleMapping:
    """Test RouterInfo tag-role mapping functionality."""

    # Tests for set_tag_role_mapping and get_tag_role_mapping removed
    # These methods are now commented out as tag-role mapping is managed internally



    def test_reset_cache(self) -> None:
        """Test resetting all caches."""
        router_info = RouterInfo()
        # Add some test data to both caches
        router_info._tag_role_cache = {"admin": ["admin"]}  # type: ignore[reportPrivateUsage, unused-ignore]
        router_info._route_cache["GET /test"] = {  # type: ignore[reportPrivateUsage, unused-ignore]
            "method": "GET",
            "path": "/test",
            "path_template": "/test",
            "name": "test",
            "tags": [],
            "allowed_roles": set(),
        }
        router_info._route_finder = MagicMock()  # type: ignore[reportPrivateUsage, unused-ignore]

        router_info.reset_cache()

        assert router_info._tag_role_cache == {}  # type: ignore[reportPrivateUsage, unused-ignore]
        assert router_info._route_cache == {}  # type: ignore[reportPrivateUsage, unused-ignore]
        assert router_info._route_finder is None  # type: ignore[reportPrivateUsage, unused-ignore]


class TestRouterInfoCacheManagement:
    """Test RouterInfo cache management functionality."""

    def test_get_router_item_success(self) -> None:
        """Test getting RouterItem by method and path."""
        router_info = RouterInfo()

        router_item: RouterItem = {
            "method": "GET",
            "path": "/api/test",
            "path_template": "/api/test",
            "name": "test",
            "tags": ["test"],
            "allowed_roles": {"user"},
        }

        router_info._route_cache["GET /api/test"] = router_item  # type: ignore[reportPrivateUsage, unused-ignore]

        result = router_info.get_router_item("GET", "/api/test")

        assert result == router_item

    def test_get_router_item_not_found(self) -> None:
        """Test getting RouterItem when not found."""
        router_info = RouterInfo()

        result = router_info.get_router_item("GET", "/api/missing")

        assert result is None
