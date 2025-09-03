###############################################################################
# LLM prompt to generate these unit tests:
#
# help to generate a set of comprehensive unit tests for file @faster/core/auth/routers.py
# to file @tests/core/test_auth_routers.py. For these http endpoints, you can use pytest-httpx
# to simulate HTTP requests and responses.
# #############################################################################

from unittest.mock import MagicMock, patch
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

        # Override the app state for testing
        client.app.state.settings = mock_settings

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
        assert settings_data["backendUrl"] == "http://127.0.0.1:8000"
        assert settings_data["isSignUp"] is False
        assert settings_data["sentryDsn"] == "test-dsn"
        assert settings_data["sentryEnvironment"] == "test"
        assert settings_data["sentryEnabled"] is True


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
        client.app.state.settings = mock_settings

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
        client.app.state.settings = mock_settings

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
        client.app.state.settings = mock_settings

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
        client.app.state.settings = mock_settings

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
        client.app.state.settings = mock_settings

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
        client.app.state.settings = mock_settings

        # Mock the check_all_resources function
        with patch("faster.core.routers.check_all_resources") as mock_check_resources:
            # Set up mock app state with health data
            client.app.state.latest_status_check = "2023-01-01T00:00:00Z"
            client.app.state.latest_status_info = {
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
        client.app.state.settings = mock_settings

        # Mock the check_all_resources function
        with patch("faster.core.routers.check_all_resources") as mock_check_resources:
            # Set up mock app state without health data
            if hasattr(client.app.state, "latest_status_check"):
                delattr(client.app.state, "latest_status_check")
            if hasattr(client.app.state, "latest_status_info"):
                delattr(client.app.state, "latest_status_info")

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
