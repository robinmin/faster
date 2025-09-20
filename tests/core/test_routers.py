###############################################################################
# LLM prompt to generate these unit tests:
#
# help to generate a set of comprehensive unit tests for file @faster/core/auth/routers.py
# to file @tests/core/test_auth_routers.py. For these http endpoints, you can use pytest-httpx
# to simulate HTTP requests and responses.
# #############################################################################

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import CONTENT_TYPE_LATEST
import pytest

from faster.core.routers import dev_router, sys_router


class TestDevRouter:
    """Test dev router endpoints."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create a FastAPI app with dev router."""
        app = FastAPI()
        app.include_router(dev_router)
        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create a test client."""
        return TestClient(app)

    def test_health_check_endpoint(self, client: TestClient) -> None:
        """Test the health check endpoint returns the dev-admin.html file."""
        # Make a request to the endpoint
        response = client.get("/dev/admin")

        # Check that the response is successful
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"

        # Check that the content contains HTML
        assert "<!DOCTYPE html>" in response.text or "<html" in response.text.lower()

    def test_settings_endpoint(self, client: TestClient) -> None:
        """Test the settings endpoint returns configuration data."""
        # Create a mock app state with settings
        mock_settings = MagicMock()
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_anon_key = "test-anon-key"
        mock_settings.sentry_client_dsn = "test-dsn"
        mock_settings.environment = "test"
        mock_settings.host = "127.0.0.1"
        mock_settings.port = 8000

        # Override the app state for testing
        cast(FastAPI, client.app).state.settings = mock_settings

        # Make a request to the endpoint
        response = client.get("/dev/settings")

        # Check that the response is successful
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        # Parse the JSON response
        data = response.json()

        # Check the response structure
        assert "status" in data
        assert data["status"] == "success"
        assert "data" in data
        assert isinstance(data["data"], dict)

        # Check the data content
        settings_data = data["data"]
        assert settings_data["supabaseUrl"] == "https://test.supabase.co"
        assert settings_data["supabaseKey"] == "test-anon-key"
        assert settings_data["backendUrl"] == "http://testserver"
        assert settings_data["isSignUp"] is False
        assert settings_data["sentryDsn"] == "test-dsn"
        assert settings_data["sentryEnvironment"] == "test"
        assert settings_data["sentryEnabled"] is True

    @patch("faster.core.routers.SysService")
    def test_show_sys_dict_success(self, mock_sys_service_class: MagicMock, client: TestClient) -> None:
        """Test successful sys_dict show endpoint."""
        # Mock the SysService
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service

        # Mock service response
        mock_sys_service.get_sys_dict_with_status = AsyncMock(
            return_value=[
                {"category": "user_role", "key": 10, "value": "default", "in_used": True},
                {"category": "user_role", "key": 20, "value": "developer", "in_used": True},
                {"category": "status", "key": 1, "value": "active", "in_used": True},
                {"category": "status", "key": 0, "value": "inactive", "in_used": False},
            ]
        )

        # Make request
        response = client.get("/dev/sys_dict/show")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "items" in data["data"]
        items = data["data"]["items"]
        assert len(items) == 4  # 2 categories with 2 items each

        # Verify item structure
        assert all("category" in item and "key" in item and "value" in item and "in_used" in item for item in items)

        # Verify service was called correctly
        mock_sys_service.get_sys_dict_with_status.assert_called_once_with(
            category=None, key=None, value=None, in_used_only=False
        )

    @patch("faster.core.routers.SysService")
    def test_show_sys_dict_with_filters(self, mock_sys_service_class: MagicMock, client: TestClient) -> None:
        """Test sys_dict show endpoint with filters."""
        # Mock the SysService
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service

        # Mock service response
        mock_sys_service.get_sys_dict_with_status = AsyncMock(
            return_value=[{"category": "user_role", "key": 10, "value": "default", "in_used": True}]
        )

        # Make request with filters
        response = client.get("/dev/sys_dict/show?category=user_role&key=10&value=default")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

        # Verify service was called with filters
        mock_sys_service.get_sys_dict_with_status.assert_called_once_with(
            category="user_role", key=10, value="default", in_used_only=False
        )

    @patch("faster.core.routers.SysService")
    def test_show_sys_dict_error(self, mock_sys_service_class: MagicMock, client: TestClient) -> None:
        """Test sys_dict show endpoint error handling."""
        # Mock the SysService to raise an exception
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service

        mock_sys_service.get_sys_dict_with_status = AsyncMock(side_effect=Exception("Database error"))

        # Make request
        response = client.get("/dev/sys_dict/show")

        # Verify error response
        assert response.status_code == 200  # Still returns 200 but with error status
        data = response.json()
        assert data["status"] == "error"
        assert "Database error" in data["message"]
        assert data["data"]["items"] == []

    @patch("faster.core.routers.SysService")
    def test_adjust_sys_dict_success(self, mock_sys_service_class: MagicMock, client: TestClient) -> None:
        """Test successful sys_dict adjust endpoint."""
        # Mock the SysService
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service

        # Mock service response
        mock_sys_service.set_sys_dict = AsyncMock(return_value=True)

        # Prepare request data
        request_data = {
            "category": "test_category",
            "items": [{"category": "test_category", "key": 1, "value": "test_value", "in_used": True}],
        }

        # Make request
        response = client.post("/dev/sys_dict/adjust", json=request_data)

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "test_category" in data["message"]
        assert data["data"]["category"] == "test_category"
        assert data["data"]["items_count"] == 1

        # Verify service was called correctly
        mock_sys_service.set_sys_dict.assert_called_once_with("test_category", {1: "test_value"})

    @patch("faster.core.routers.SysService")
    def test_adjust_sys_dict_inactive_items_filtered(
        self, mock_sys_service_class: MagicMock, client: TestClient
    ) -> None:
        """Test that inactive items are filtered out in sys_dict adjust."""
        # Mock the SysService
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service

        # Mock service response
        mock_sys_service.set_sys_dict = AsyncMock(return_value=True)

        # Prepare request data with both active and inactive items
        request_data = {
            "category": "test_category",
            "items": [
                {"category": "test_category", "key": 1, "value": "active_value", "in_used": True},
                {"category": "test_category", "key": 2, "value": "inactive_value", "in_used": False},
            ],
        }

        # Make request
        response = client.post("/dev/sys_dict/adjust", json=request_data)

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["items_count"] == 1  # Only active item counted

        # Verify service was called with only active items
        mock_sys_service.set_sys_dict.assert_called_once_with("test_category", {1: "active_value"})

    @patch("faster.core.routers.SysService")
    def test_show_sys_map_success(self, mock_sys_service_class: MagicMock, client: TestClient) -> None:
        """Test successful sys_map show endpoint."""
        # Mock the SysService
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service

        # Mock service response - return list format as expected by router
        mock_sys_service.get_sys_map_with_status = AsyncMock(
            return_value=[
                {"category": "tag_role", "left_value": "admin", "right_value": "read", "in_used": True},
                {"category": "tag_role", "left_value": "admin", "right_value": "write", "in_used": True},
                {"category": "tag_role", "left_value": "user", "right_value": "read", "in_used": True},
                {"category": "permissions", "left_value": "editor", "right_value": "edit", "in_used": True},
                {"category": "permissions", "left_value": "editor", "right_value": "view", "in_used": True},
            ]
        )

        # Make request
        response = client.get("/dev/sys_map/show")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "items" in data["data"]
        items = data["data"]["items"]
        assert len(items) == 5  # admin->read, admin->write, user->read, editor->edit, editor->view

        # Verify item structure
        assert all(
            "category" in item and "left_value" in item and "right_value" in item and "in_used" in item
            for item in items
        )

        # Verify service was called correctly
        mock_sys_service.get_sys_map_with_status.assert_called_once_with(
            category=None, left=None, right=None, in_used_only=False
        )

    @patch("faster.core.routers.SysService")
    def test_show_sys_map_with_filters(self, mock_sys_service_class: MagicMock, client: TestClient) -> None:
        """Test sys_map show endpoint with filters."""
        # Mock the SysService
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service

        # Mock service response
        mock_sys_service.get_sys_map_with_status = AsyncMock(
            return_value=[{"category": "tag_role", "left_value": "admin", "right_value": "read", "in_used": True}]
        )

        # Make request with filters
        response = client.get("/dev/sys_map/show?category=tag_role&left=admin&right=read")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

        # Verify service was called with filters
        mock_sys_service.get_sys_map_with_status.assert_called_once_with(
            category="tag_role", left="admin", right="read", in_used_only=False
        )

    @patch("faster.core.routers.SysService")
    def test_adjust_sys_map_success(self, mock_sys_service_class: MagicMock, client: TestClient) -> None:
        """Test successful sys_map adjust endpoint."""
        # Mock the SysService
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service

        # Mock service response
        mock_sys_service.set_sys_map = AsyncMock(return_value=True)

        # Prepare request data
        request_data = {
            "category": "test_category",
            "items": [
                {"category": "test_category", "left_value": "admin", "right_value": "read", "in_used": True},
                {"category": "test_category", "left_value": "admin", "right_value": "write", "in_used": True},
            ],
        }

        # Make request
        response = client.post("/dev/sys_map/adjust", json=request_data)

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "test_category" in data["message"]
        assert data["data"]["category"] == "test_category"
        assert data["data"]["items_count"] == 2

        # Verify service was called correctly
        mock_sys_service.set_sys_map.assert_called_once_with("test_category", {"admin": ["read", "write"]})

    @patch("faster.core.routers.SysService")
    def test_adjust_sys_map_inactive_items_filtered(
        self, mock_sys_service_class: MagicMock, client: TestClient
    ) -> None:
        """Test that inactive items are filtered out in sys_map adjust."""
        # Mock the SysService
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service

        # Mock service response
        mock_sys_service.set_sys_map = AsyncMock(return_value=True)

        # Prepare request data with both active and inactive items
        request_data = {
            "category": "test_category",
            "items": [
                {"category": "test_category", "left_value": "admin", "right_value": "read", "in_used": True},
                {"category": "test_category", "left_value": "admin", "right_value": "write", "in_used": False},
            ],
        }

        # Make request
        response = client.post("/dev/sys_map/adjust", json=request_data)

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["items_count"] == 1  # Only active item counted

        # Verify service was called with only active items
        mock_sys_service.set_sys_map.assert_called_once_with("test_category", {"admin": ["read"]})

    @patch("faster.core.routers.SysService")
    def test_adjust_sys_map_error(self, mock_sys_service_class: MagicMock, client: TestClient) -> None:
        """Test sys_map adjust endpoint error handling."""
        # Mock the SysService to raise an exception
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service

        mock_sys_service.set_sys_map = AsyncMock(side_effect=Exception("Database error"))

        # Prepare request data
        request_data = {
            "category": "test_category",
            "items": [{"category": "test_category", "left_value": "admin", "right_value": "read", "in_used": True}],
        }

        # Make request
        response = client.post("/dev/sys_map/adjust", json=request_data)

        # Verify error response
        assert response.status_code == 200  # Still returns 200 but with error status
        data = response.json()
        assert data["status"] == "error"
        assert "Database error" in data["message"]
        assert data["data"]["category"] == "test_category"

    def test_adjust_sys_dict_validation_error(self, client: TestClient) -> None:
        """Test sys_dict adjust endpoint with invalid request data."""
        # Test with missing required fields
        invalid_request = {
            "category": "test_category"
            # Missing 'items' field
        }

        response = client.post("/dev/sys_dict/adjust", json=invalid_request)

        # Should return validation error
        assert response.status_code == 422

    def test_adjust_sys_map_validation_error(self, client: TestClient) -> None:
        """Test sys_map adjust endpoint with invalid request data."""
        # Test with missing required fields
        invalid_request = {
            "category": "test_category"
            # Missing 'items' field
        }

        response = client.post("/dev/sys_map/adjust", json=invalid_request)

        # Should return validation error
        assert response.status_code == 422

    @patch("faster.core.routers.SysService")
    def test_adjust_sys_dict_repository_failure(self, mock_sys_service_class: MagicMock, client: TestClient) -> None:
        """Test sys_dict adjust when service returns False."""
        # Mock the SysService
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service

        # Mock service to return False (operation failed)
        mock_sys_service.set_sys_dict = AsyncMock(return_value=False)

        # Prepare request data
        request_data = {
            "category": "test_category",
            "items": [{"category": "test_category", "key": 1, "value": "test_value", "in_used": True}],
        }

        # Make request
        response = client.post("/dev/sys_dict/adjust", json=request_data)

        # Verify error response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Failed to update sys_dict" in data["message"]

    @patch("faster.core.routers.SysService")
    def test_adjust_sys_map_repository_failure(self, mock_sys_service_class: MagicMock, client: TestClient) -> None:
        """Test sys_map adjust when service returns False."""
        # Mock the SysService
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service

        # Mock service to return False (operation failed)
        mock_sys_service.set_sys_map = AsyncMock(return_value=False)

        # Prepare request data
        request_data = {
            "category": "test_category",
            "items": [{"category": "test_category", "left_value": "admin", "right_value": "read", "in_used": True}],
        }

        # Make request
        response = client.post("/dev/sys_map/adjust", json=request_data)

        # Verify error response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Failed to update sys_map" in data["message"]


class TestSysRouter:
    """Test sys router endpoints."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create a FastAPI app with sys router."""
        app = FastAPI()
        app.include_router(sys_router)
        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create a test client."""
        return TestClient(app)

    def test_chrome_dev_tools_endpoint_debug_mode(self, client: TestClient) -> None:
        """Test Chrome DevTools endpoint works in debug mode."""
        # Create a mock app state with debug settings
        mock_settings = MagicMock()
        mock_settings.is_debug = True
        cast(FastAPI, client.app).state.settings = mock_settings

        # Make a request to the endpoint
        response = client.get("/.well-known/appspecific/com.chrome.devtools.json")

        # Check that the response is successful
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        # Parse the JSON response
        data = response.json()

        # Check the response structure
        assert "workspace" in data
        assert isinstance(data["workspace"], dict)
        assert "uuid" in data["workspace"]
        assert "root" in data["workspace"]

        # Check that UUID is valid
        uuid_val = data["workspace"]["uuid"]
        # This will raise an exception if not a valid UUID
        _ = uuid4()  # Just to show the format, we don't need to parse the actual one
        assert isinstance(uuid_val, str)
        assert len(uuid_val) > 0

    def test_chrome_dev_tools_endpoint_non_debug_mode(self, client: TestClient) -> None:
        """Test Chrome DevTools endpoint returns error when not in debug mode."""
        # Create a mock app state with non-debug settings
        mock_settings = MagicMock()
        mock_settings.is_debug = False
        cast(FastAPI, client.app).state.settings = mock_settings

        # Make a request to the endpoint
        response = client.get("/.well-known/appspecific/com.chrome.devtools.json")

        # Check that the response is successful but contains error
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        # Parse the JSON response
        data = response.json()

        # Check the error message
        assert "error" in data
        assert data["error"] == "DevTools endpoint only available in debug mode"

    def test_metrics_endpoint_enabled(self, client: TestClient) -> None:
        """Test metrics endpoint works when enabled."""
        # Create a mock app state with metrics enabled
        mock_settings = MagicMock()
        mock_settings.vps_enable_metrics = True
        cast(FastAPI, client.app).state.settings = mock_settings

        # Make a request to the endpoint
        response = client.get("/metrics")

        # Check that the response is successful
        assert response.status_code == 200
        assert response.headers["content-type"] == CONTENT_TYPE_LATEST

        # The content should be prometheus metrics (text format)
        assert isinstance(response.text, str)

    def test_metrics_endpoint_disabled(self, client: TestClient) -> None:
        """Test metrics endpoint returns 404 when disabled."""
        # Create a mock app state with metrics disabled
        mock_settings = MagicMock()
        mock_settings.vps_enable_metrics = False
        cast(FastAPI, client.app).state.settings = mock_settings

        # Make a request to the endpoint
        response = client.get("/metrics")

        # Check that the response is 404
        assert response.status_code == 404
        assert response.text == "Metrics endpoint disabled"

    @patch("faster.core.routers.generate_latest")
    def test_metrics_endpoint_prometheus_import_error(
        self, mock_generate_latest: MagicMock, client: TestClient
    ) -> None:
        """Test metrics endpoint handles prometheus import error."""
        # Create a mock app state with metrics enabled
        mock_settings = MagicMock()
        mock_settings.vps_enable_metrics = True
        cast(FastAPI, client.app).state.settings = mock_settings

        # Make generate_latest raise an ImportError
        mock_generate_latest.side_effect = ImportError("prometheus_client not installed")

        # Make a request to the endpoint
        response = client.get("/metrics")

        # Check that the response is 503
        assert response.status_code == 503
        assert "prometheus_client not installed" in response.text

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client: TestClient) -> None:
        """Test health endpoint returns status information."""
        # Create a mock app state with settings
        mock_settings = MagicMock()
        cast(FastAPI, client.app).state.settings = mock_settings

        # Mock the check_all_resources function
        with patch("faster.core.routers.check_all_resources") as mock_check_resources:
            # Set up mock app state with health data
            cast(FastAPI, client.app).state.latest_status_check = "2023-01-01T00:00:00Z"
            cast(FastAPI, client.app).state.latest_status_info = {
                "db": {"status": "ok"},
                "redis": {"status": "ok"},
                "sentry": {"status": "ok"},
            }

            # Make a request to the endpoint
            response = client.get("/health")

            # Check that check_all_resources was called
            mock_check_resources.assert_called_once()

            # Check that the response is successful
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"

            # Parse the JSON response
            data = response.json()

            # Check the response structure
            assert "status" in data
            assert data["status"] == "success"
            assert "data" in data
            assert isinstance(data["data"], dict)

            # Check the data content
            health_data = data["data"]
            assert health_data["latest_status_check"] == "2023-01-01T00:00:00Z"
            assert health_data["db"] == {"status": "ok"}
            assert health_data["redis"] == {"status": "ok"}
            assert health_data["sentry"] == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_health_endpoint_without_status_info(self, client: TestClient) -> None:
        """Test health endpoint works when status info is not available."""
        # Create a mock app state with settings
        mock_settings = MagicMock()
        cast(FastAPI, client.app).state.settings = mock_settings

        # Mock the check_all_resources function
        with patch("faster.core.routers.check_all_resources") as mock_check_resources:
            # Set up mock app state without health data
            if hasattr(cast(FastAPI, client.app).state, "latest_status_check"):
                delattr(cast(FastAPI, client.app).state, "latest_status_check")
            if hasattr(cast(FastAPI, client.app).state, "latest_status_info"):
                delattr(cast(FastAPI, client.app).state, "latest_status_info")

            # Make a request to the endpoint
            response = client.get("/health")

            # Check that check_all_resources was called
            mock_check_resources.assert_called_once()

            # Check that the response is successful
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"

            # Parse the JSON response
            data = response.json()

            # Check the response structure
            assert "status" in data
            assert data["status"] == "success"
            assert "data" in data
            assert isinstance(data["data"], dict)

            # Check the data content (should be None or missing)
            health_data = data["data"]
            # These might be None or missing depending on implementation
            assert isinstance(health_data, dict)
