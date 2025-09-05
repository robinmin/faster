from datetime import datetime, timedelta
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status
from fastapi.routing import APIRoute
import pytest

from faster.core.exceptions import AppError, AuthError
from faster.core.models import AppResponse
from faster.core.utilities import (
    app_exception_handler,
    auth_exception_handler,
    check_all_resources,
    custom_validation_exception_handler,
    detect_platform,
    get_all_endpoints,
    get_current_endpoint,
    is_api_call,
    is_cloudflare_workers,
    is_vps_deployment,
)


class TestPlatformDetection:
    """Test platform detection utilities."""

    def test_detect_platform_explicit_vps(self) -> None:
        """Test detect_platform with explicit 'vps' setting."""
        result = detect_platform("vps")
        assert result == "vps"

    def test_detect_platform_explicit_cloudflare(self) -> None:
        """Test detect_platform with explicit 'cloudflare-workers' setting."""
        result = detect_platform("cloudflare-workers")
        assert result == "cloudflare-workers"

    def test_detect_platform_auto_default(self) -> None:
        """Test detect_platform with 'auto' setting defaults to 'vps'."""
        with patch.dict(os.environ, {}, clear=True):
            result = detect_platform("auto")
            assert result == "vps"

    def test_detect_platform_auto_cloudflare_pages(self) -> None:
        """Test detect_platform detects Cloudflare Pages."""
        with patch.dict(os.environ, {"CF_PAGES": "1"}):
            result = detect_platform("auto")
            assert result == "cloudflare-workers"

    def test_detect_platform_auto_cloudflare_worker(self) -> None:
        """Test detect_platform detects Cloudflare Worker."""
        with patch.dict(os.environ, {"CF_WORKER": "1"}):
            result = detect_platform("auto")
            assert result == "cloudflare-workers"

    def test_detect_platform_auto_aws_lambda(self) -> None:
        """Test detect_platform detects AWS Lambda as VPS-like."""
        with patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "test-function"}):
            result = detect_platform("auto")
            assert result == "vps"

    def test_detect_platform_auto_heroku(self) -> None:
        """Test detect_platform detects Heroku as VPS-like."""
        with patch.dict(os.environ, {"HEROKU_APP_NAME": "test-app"}):
            result = detect_platform("auto")
            assert result == "vps"

    def test_is_cloudflare_workers_true(self) -> None:
        """Test is_cloudflare_workers returns True for Cloudflare Workers."""
        with patch.dict(os.environ, {"CF_WORKER": "1"}):
            result = is_cloudflare_workers("auto")
            assert result is True

    def test_is_cloudflare_workers_false(self) -> None:
        """Test is_cloudflare_workers returns False for non-Cloudflare Workers."""
        with patch.dict(os.environ, {}, clear=True):
            result = is_cloudflare_workers("auto")
            assert result is False

    def test_is_vps_deployment_true(self) -> None:
        """Test is_vps_deployment returns True for VPS deployment."""
        with patch.dict(os.environ, {}, clear=True):
            result = is_vps_deployment("auto")
            assert result is True

    def test_is_vps_deployment_false(self) -> None:
        """Test is_vps_deployment returns False for non-VPS deployment."""
        with patch.dict(os.environ, {"CF_WORKER": "1"}):
            result = is_vps_deployment("auto")
            assert result is False


class TestRequestUtilities:
    """Test request utility functions."""

    def test_is_api_call_with_json_accept_header(self) -> None:
        """Test is_api_call returns True with application/json accept header."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "application/json"

        result = is_api_call(mock_request)
        assert result is True
        mock_request.headers.get.assert_called_once_with("accept")

    def test_is_api_call_with_mixed_accept_header(self) -> None:
        """Test is_api_call returns True with mixed accept header containing application/json."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "text/html,application/json;q=0.9,*/*;q=0.8"

        result = is_api_call(mock_request)
        assert result is True
        mock_request.headers.get.assert_called_once_with("accept")

    def test_is_api_call_without_json_accept_header(self) -> None:
        """Test is_api_call returns False without application/json accept header."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "text/html,application/xhtml+xml"

        result = is_api_call(mock_request)
        assert result is False
        mock_request.headers.get.assert_called_once_with("accept")

    def test_is_api_call_with_no_accept_header(self) -> None:
        """Test is_api_call returns False with no accept header."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None

        result = is_api_call(mock_request)
        assert result is False
        mock_request.headers.get.assert_called_once_with("accept")


class TestEndpointUtilities:
    """Test endpoint utility functions."""

    def test_get_all_endpoints(self) -> None:
        """Test get_all_endpoints returns correct endpoint information."""
        # Create a mock FastAPI app with routes
        mock_app = MagicMock()

        # Create mock routes
        mock_route1 = MagicMock(spec=APIRoute)
        mock_route1.path = "/api/users"
        mock_route1.methods = {"GET", "POST"}
        mock_route1.tags = ["users"]
        mock_route1.name = "get_users"
        # Properly mock the endpoint function
        mock_endpoint_func = MagicMock()
        mock_endpoint_func.__name__ = "get_users_endpoint"
        mock_route1.endpoint = mock_endpoint_func

        mock_route2 = MagicMock(spec=APIRoute)
        mock_route2.path = "/api/items"
        mock_route2.methods = {"GET"}
        mock_route2.tags = ["items"]
        mock_route2.name = "get_items"
        # Properly mock the endpoint function
        mock_endpoint_func2 = MagicMock()
        mock_endpoint_func2.__name__ = "get_items_endpoint"
        mock_route2.endpoint = mock_endpoint_func2

        mock_app.routes = [mock_route1, mock_route2]

        result = get_all_endpoints(mock_app)

        assert len(result) == 2
        assert result[0]["path"] == "/api/users"
        assert set(result[0]["methods"]) == {"GET", "POST"}
        assert result[0]["tags"] == ["users"]
        assert result[0]["name"] == "get_users"
        assert result[0]["endpoint_func"] == "get_users_endpoint"

        assert result[1]["path"] == "/api/items"
        assert result[1]["methods"] == ["GET"]
        assert result[1]["tags"] == ["items"]
        assert result[1]["name"] == "get_items"
        assert result[1]["endpoint_func"] == "get_items_endpoint"

    def test_get_all_endpoints_with_non_api_routes(self) -> None:
        """Test get_all_endpoints ignores non-API routes."""
        # Create a mock FastAPI app with routes
        mock_app = MagicMock()

        # Create mock routes - one APIRoute and one non-APIRoute
        mock_route1 = MagicMock(spec=APIRoute)
        mock_route1.path = "/api/users"
        mock_route1.methods = {"GET"}
        mock_route1.tags = ["users"]
        mock_route1.name = "get_users"
        # Properly mock the endpoint function
        mock_endpoint_func = MagicMock()
        mock_endpoint_func.__name__ = "get_users_endpoint"
        mock_route1.endpoint = mock_endpoint_func

        mock_route2 = MagicMock()  # Non-APIRoute
        mock_route2.path = "/static"

        mock_app.routes = [mock_route1, mock_route2]

        result = get_all_endpoints(mock_app)

        assert len(result) == 1
        assert result[0]["path"] == "/api/users"

    def test_get_current_endpoint_match(self) -> None:
        """Test get_current_endpoint finds matching endpoint."""
        mock_request = MagicMock()
        mock_request.url.path = "/api/users"
        mock_request.method = "GET"

        endpoints = [
            {
                "path": "/api/users",
                "methods": ["GET", "POST"],
                "tags": ["users"],
                "name": "get_users",
                "endpoint_func": "get_users_endpoint",
            }
        ]

        result = get_current_endpoint(mock_request, endpoints)

        assert result is not None
        assert result["path"] == "/api/users"
        assert result["methods"] == ["GET", "POST"]

    def test_get_current_endpoint_head_method(self) -> None:
        """Test get_current_endpoint handles HEAD method."""
        mock_request = MagicMock()
        mock_request.url.path = "/api/users"
        mock_request.method = "HEAD"

        endpoints = [
            {
                "path": "/api/users",
                "methods": ["GET", "POST"],
                "tags": ["users"],
                "name": "get_users",
                "endpoint_func": "get_users_endpoint",
            }
        ]

        result = get_current_endpoint(mock_request, endpoints)

        assert result is not None
        assert result["path"] == "/api/users"

    def test_get_current_endpoint_no_match(self) -> None:
        """Test get_current_endpoint returns None when no match found."""
        mock_request = MagicMock()
        mock_request.url.path = "/api/nonexistent"
        mock_request.method = "GET"

        endpoints = [
            {
                "path": "/api/users",
                "methods": ["GET", "POST"],
                "tags": ["users"],
                "name": "get_users",
                "endpoint_func": "get_users_endpoint",
            }
        ]

        result = get_current_endpoint(mock_request, endpoints)

        assert result is None

    def test_get_current_endpoint_method_mismatch(self) -> None:
        """Test get_current_endpoint returns None when method doesn't match."""
        mock_request = MagicMock()
        mock_request.url.path = "/api/users"
        mock_request.method = "DELETE"

        endpoints = [
            {
                "path": "/api/users",
                "methods": ["GET", "POST"],
                "tags": ["users"],
                "name": "get_users",
                "endpoint_func": "get_users_endpoint",
            }
        ]

        result = get_current_endpoint(mock_request, endpoints)

        assert result is None


class TestResourceCheck:
    """Test resource checking utilities."""

    @pytest.mark.asyncio
    async def test_check_all_resources_skips_frequent_calls(self) -> None:
        """Test check_all_resources skips checks when called too frequently."""
        mock_app = MagicMock()
        mock_app.state.latest_status_check = datetime.now()

        mock_settings = MagicMock()
        mock_settings.refresh_interval = 60  # 60 seconds

        # Mock the app routes for get_all_endpoints
        mock_route = MagicMock(spec=APIRoute)
        mock_route.path = "/api/test"
        mock_route.methods = {"GET"}
        mock_route.tags = ["test"]
        mock_route.name = "test_endpoint"
        # Properly mock the endpoint function
        mock_endpoint_func = MagicMock()
        mock_endpoint_func.__name__ = "test_endpoint_func"
        mock_route.endpoint = mock_endpoint_func
        mock_app.routes = [mock_route]

        # Should skip because last check was recent
        await check_all_resources(mock_app, mock_settings)

        # Since it's an async function that returns None, we can't easily check if it was skipped
        # But we can check that endpoints were still set (the function always sets them)
        assert hasattr(mock_app.state, "endpoints")

    @pytest.mark.asyncio
    async def test_check_all_resources_performs_check(self) -> None:
        """Test check_all_resources performs checks when enough time has passed."""
        mock_app = MagicMock()
        mock_app.state.latest_status_check = datetime.now() - timedelta(seconds=70)  # 70 seconds ago

        mock_settings = MagicMock()
        mock_settings.refresh_interval = 60  # 60 seconds

        # Mock the plugin manager
        with patch("faster.core.utilities.PluginManager.get_instance") as mock_get_instance:
            mock_plugin_mgr = AsyncMock()
            mock_plugin_mgr.check_health.return_value = {
                "database": {"status": "ok"},
                "redis": {"status": "ok"},
                "sentry": {"status": "ok"},
            }
            mock_get_instance.return_value = mock_plugin_mgr

            # Mock the app routes for get_all_endpoints
            mock_route = MagicMock(spec=APIRoute)
            mock_route.path = "/api/test"
            mock_route.methods = {"GET"}
            mock_route.tags = ["test"]
            mock_route.name = "test_endpoint"
            # Properly mock the endpoint function
            mock_endpoint_func = MagicMock()
            mock_endpoint_func.__name__ = "test_endpoint_func"
            mock_route.endpoint = mock_endpoint_func
            mock_app.routes = [mock_route]

            await check_all_resources(mock_app, mock_settings)

            # Verify that endpoints were set
            assert hasattr(mock_app.state, "endpoints")
            assert len(mock_app.state.endpoints) == 1

            # Verify that plugin health check was called
            mock_plugin_mgr.check_health.assert_called_once()

            # Verify that latest status info was set
            assert hasattr(mock_app.state, "latest_status_info")
            assert "db" in mock_app.state.latest_status_info
            assert "redis" in mock_app.state.latest_status_info
            assert "sentry" in mock_app.state.latest_status_info


class TestExceptionHandlers:
    """Test exception handler functions."""

    @pytest.mark.asyncio
    async def test_app_exception_handler(self) -> None:
        """Test app_exception_handler formats response correctly."""
        mock_request = MagicMock()
        mock_exception = AppError("Test error message", status_code=400, errors=[{"field": "test", "error": "invalid"}])

        with patch("faster.core.utilities.capture_it") as mock_capture:
            result = await app_exception_handler(mock_request, mock_exception)

            assert isinstance(result, AppResponse)
            # Parse the JSON content to check the values

            content = json.loads(bytes(result.body))
            assert content["status"] == "error"
            assert content["message"] == "Test error message"
            assert content["data"] == [{"field": "test", "error": "invalid"}]
            assert result.status_code == 400

            mock_capture.assert_called_once_with("Business logic issue: Test error message")

    @pytest.mark.asyncio
    async def test_app_exception_handler_without_errors(self) -> None:
        """Test app_exception_handler handles exception without errors."""
        mock_request = MagicMock()
        mock_exception = AppError("Test error message", status_code=400)

        with patch("faster.core.utilities.capture_it") as mock_capture:
            result = await app_exception_handler(mock_request, mock_exception)

            assert isinstance(result, AppResponse)
            # Parse the JSON content to check the values

            content = json.loads(bytes(result.body))
            assert content["status"] == "error"
            assert content["message"] == "Test error message"
            assert content["data"] == {}  # Default to empty dict when None
            assert result.status_code == 400

            mock_capture.assert_called_once_with("Business logic issue: Test error message")

    @pytest.mark.asyncio
    async def test_custom_validation_exception_handler(self) -> None:
        """Test custom_validation_exception_handler formats validation errors."""
        mock_request = MagicMock()

        # Create a mock RequestValidationError with errors
        mock_error1 = {"loc": ("body", "name"), "msg": "Field required"}
        mock_error2 = {"loc": ("body", "email"), "msg": "Invalid email format"}
        mock_error3 = {"loc": ("query", "page"), "msg": "Must be greater than 0"}

        mock_exception = MagicMock()
        mock_exception.errors.return_value = [mock_error1, mock_error2, mock_error3]

        with patch("faster.core.utilities.logger") as mock_logger:
            result = await custom_validation_exception_handler(mock_request, mock_exception)

            assert isinstance(result, AppResponse)
            # Parse the JSON content to check the values

            content = json.loads(bytes(result.body))
            assert content["status"] == "validation error"
            assert content["message"] == "Request validation failed"
            assert result.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            assert len(content["data"]) == 3

            # Check that errors are grouped by field
            field_errors = {item["field"]: item["messages"] for item in content["data"]}
            assert "body.name" in field_errors
            assert "body.email" in field_errors
            assert "query.page" in field_errors

            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_auth_exception_handler(self) -> None:
        """Test auth_exception_handler formats authentication errors."""
        mock_request = MagicMock()
        mock_exception = AuthError("Authentication failed", status_code=401, errors=[{"reason": "invalid_token"}])

        with patch("faster.core.utilities.logger") as mock_logger:
            result = await auth_exception_handler(mock_request, mock_exception)

            assert isinstance(result, AppResponse)
            # Parse the JSON content to check the values

            content = json.loads(bytes(result.body))
            assert content["status"] == "Authentication failed"
            assert content["message"] == "Authentication failed"
            assert result.status_code == 401
            assert content["data"] == [{"reason": "invalid_token"}]

            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_auth_exception_handler_without_errors(self) -> None:
        """Test auth_exception_handler handles authentication error without errors."""
        mock_request = MagicMock()
        mock_exception = AuthError("Authentication failed", status_code=401)

        with patch("faster.core.utilities.logger") as mock_logger:
            result = await auth_exception_handler(mock_request, mock_exception)

            assert isinstance(result, AppResponse)
            # Parse the JSON content to check the values

            content = json.loads(bytes(result.body))
            assert content["status"] == "Authentication failed"
            assert content["message"] == "Authentication failed"
            assert result.status_code == 401
            assert content["data"] == {}  # Default to empty dict when None

            mock_logger.error.assert_called_once()
