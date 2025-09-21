###############################################################################
# LLM prompt to generate these unit tests:
#
# help to generate a set of comprehensive unit tests for file @faster/core/auth/routers.py
# to file @tests/core/test_auth_routers.py. For these http endpoints, you can use pytest-httpx
# to simulate HTTP requests and responses.
# #############################################################################

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from faster.core.routers import dev_router


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
        response = client.post("/dev/sys_dict/show", json={
            "category": None,
            "key": None,
            "value": None,
            "in_used_only": False
        })

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
        response = client.post("/dev/sys_dict/show", json={
            "category": "user_role",
            "key": 10,
            "value": "default",
            "in_used_only": False
        })

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
        response = client.post("/dev/sys_dict/show", json={
            "category": None,
            "key": None,
            "value": None,
            "in_used_only": False
        })

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
        response = client.post("/dev/sys_map/show", json={
            "category": None,
            "left_value": None,
            "right_value": None,
            "in_used_only": False
        })

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
        response = client.post("/dev/sys_map/show", json={
            "category": "tag_role",
            "left_value": "admin",
            "right_value": "read",
            "in_used_only": False
        })

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

    @patch("faster.core.routers.SysService")
    def test_hard_delete_sys_dict_entry_success(self, mock_sys_service_class: MagicMock, client: TestClient) -> None:
        """Test successful hard delete sys_dict entry endpoint."""
        # Mock the service
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service
        mock_sys_service.hard_delete_sys_dict_entry = AsyncMock(return_value=True)

        # Make request
        response = client.request("DELETE", "/dev/sys_dict/delete", json={
            "category": "test_category",
            "key": 1,
            "value": "test_value"
        })

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "Successfully deleted sys_dict entry" in data["message"]
        assert data["data"]["category"] == "test_category"
        assert data["data"]["key"] == 1
        assert data["data"]["value"] == "test_value"

        # Verify service was called
        mock_sys_service.hard_delete_sys_dict_entry.assert_called_once_with("test_category", 1, "test_value")

    @patch("faster.core.routers.SysService")
    def test_hard_delete_sys_dict_entry_not_found(self, mock_sys_service_class: MagicMock, client: TestClient) -> None:
        """Test hard delete sys_dict entry when entry not found."""
        # Mock the service
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service
        mock_sys_service.hard_delete_sys_dict_entry = AsyncMock(return_value=False)

        # Make request
        response = client.request("DELETE", "/dev/sys_dict/delete", json={
            "category": "test_category",
            "key": 1,
            "value": "test_value"
        })

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Entry not found or failed to delete" in data["message"]
        assert data["data"]["category"] == "test_category"
        assert data["data"]["key"] == 1
        assert data["data"]["value"] == "test_value"

    @patch("faster.core.routers.SysService")
    def test_hard_delete_sys_dict_entry_error(self, mock_sys_service_class: MagicMock, client: TestClient) -> None:
        """Test hard delete sys_dict entry error handling."""
        # Mock the service
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service
        mock_sys_service.hard_delete_sys_dict_entry = AsyncMock(side_effect=Exception("Database error"))

        # Make request
        response = client.request("DELETE", "/dev/sys_dict/delete", json={
            "category": "test_category",
            "key": 1,
            "value": "test_value"
        })

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Failed to hard delete sys_dict entry" in data["message"]
        assert data["data"]["category"] == "test_category"
        assert data["data"]["key"] == 1
        assert data["data"]["value"] == "test_value"

    @patch("faster.core.routers.SysService")
    def test_hard_delete_sys_map_entry_success(self, mock_sys_service_class: MagicMock, client: TestClient) -> None:
        """Test successful hard delete sys_map entry endpoint."""
        # Mock the service
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service
        mock_sys_service.hard_delete_sys_map_entry = AsyncMock(return_value=True)

        # Make request
        response = client.request("DELETE", "/dev/sys_map/delete", json={
            "category": "test_category",
            "left_value": "admin",
            "right_value": "read"
        })

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "Successfully deleted sys_map entry" in data["message"]
        assert data["data"]["category"] == "test_category"
        assert data["data"]["left_value"] == "admin"
        assert data["data"]["right_value"] == "read"

        # Verify service was called
        mock_sys_service.hard_delete_sys_map_entry.assert_called_once_with("test_category", "admin", "read")

    @patch("faster.core.routers.SysService")
    def test_hard_delete_sys_map_entry_not_found(self, mock_sys_service_class: MagicMock, client: TestClient) -> None:
        """Test hard delete sys_map entry when entry not found."""
        # Mock the service
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service
        mock_sys_service.hard_delete_sys_map_entry = AsyncMock(return_value=False)

        # Make request
        response = client.request("DELETE", "/dev/sys_map/delete", json={
            "category": "test_category",
            "left_value": "admin",
            "right_value": "read"
        })

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Entry not found or failed to delete" in data["message"]
        assert data["data"]["category"] == "test_category"
        assert data["data"]["left_value"] == "admin"
        assert data["data"]["right_value"] == "read"

    @patch("faster.core.routers.SysService")
    def test_hard_delete_sys_map_entry_error(self, mock_sys_service_class: MagicMock, client: TestClient) -> None:
        """Test hard delete sys_map entry error handling."""
        # Mock the service
        mock_sys_service = MagicMock()
        mock_sys_service_class.return_value = mock_sys_service
        mock_sys_service.hard_delete_sys_map_entry = AsyncMock(side_effect=Exception("Database error"))

        # Make request
        response = client.request("DELETE", "/dev/sys_map/delete", json={
            "category": "test_category",
            "left_value": "admin",
            "right_value": "read"
        })

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Failed to hard delete sys_map entry" in data["message"]
        assert data["data"]["category"] == "test_category"
        assert data["data"]["left_value"] == "admin"
        assert data["data"]["right_value"] == "read"

    @pytest.mark.asyncio
    async def test_dev_hard_delete_sys_dict_entry_success(self, client: TestClient) -> None:
        """Test successful hard delete of sys_dict entry."""
        # Mock the SysService
        with patch("faster.core.routers.SysService") as mock_sys_service_class:
            mock_sys_service = MagicMock()
            mock_sys_service_class.return_value = mock_sys_service
            mock_sys_service.hard_delete_sys_dict_entry = AsyncMock(return_value=True)

            # Make a DELETE request to the endpoint
            response = client.request("DELETE", "/dev/sys_dict/delete", json={
                "category": "test_cat",
                "key": 1,
                "value": "test_value"
            })

            # Check that the response is successful
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"

            # Parse the JSON response
            data = response.json()

            # Check the response structure
            assert data["status"] == "success"
            assert "Successfully deleted sys_dict entry" in data["message"]
            assert data["data"]["category"] == "test_cat"
            assert data["data"]["key"] == 1
            assert data["data"]["value"] == "test_value"

            # Verify the service method was called correctly
            mock_sys_service.hard_delete_sys_dict_entry.assert_called_once_with("test_cat", 1, "test_value")
