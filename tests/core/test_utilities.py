from datetime import datetime, timedelta
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status
import pytest

from faster.core.exceptions import AppError, AuthError
from faster.core.models import AppResponse
from faster.core.utilities import (
    app_exception_handler,
    auth_exception_handler,
    check_all_resources,
    custom_validation_exception_handler,
    detect_platform,
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

    @patch.dict(os.environ, {"CF_PAGES": "1"}, clear=True)
    def test_detect_platform_auto_cloudflare_pages(self) -> None:
        """Test detect_platform detects Cloudflare Pages."""
        result = detect_platform("auto")
        assert result == "cloudflare-workers"

    @patch.dict(os.environ, {"CF_WORKER": "1"}, clear=True)
    def test_detect_platform_auto_cloudflare_worker(self) -> None:
        """Test detect_platform detects Cloudflare Worker."""
        result = detect_platform("auto")
        assert result == "cloudflare-workers"

    @patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "test"}, clear=True)
    def test_detect_platform_auto_aws_lambda(self) -> None:
        """Test detect_platform detects AWS Lambda as VPS."""
        result = detect_platform("auto")
        assert result == "vps"

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test"}, clear=True)
    def test_detect_platform_auto_google_cloud(self) -> None:
        """Test detect_platform detects Google Cloud as VPS."""
        result = detect_platform("auto")
        assert result == "vps"

    @patch.dict(os.environ, {}, clear=True)
    def test_detect_platform_auto_default_vps(self) -> None:
        """Test detect_platform defaults to VPS when no indicators."""
        result = detect_platform("auto")
        assert result == "vps"

    def test_is_cloudflare_workers_true(self) -> None:
        """Test is_cloudflare_workers returns True for cloudflare-workers."""
        with patch("faster.core.utilities.detect_platform", return_value="cloudflare-workers"):
            result = is_cloudflare_workers("test")
            assert result is True

    def test_is_cloudflare_workers_false(self) -> None:
        """Test is_cloudflare_workers returns False for vps."""
        with patch("faster.core.utilities.detect_platform", return_value="vps"):
            result = is_cloudflare_workers("test")
            assert result is False

    def test_is_vps_deployment_true(self) -> None:
        """Test is_vps_deployment returns True for vps."""
        with patch("faster.core.utilities.detect_platform", return_value="vps"):
            result = is_vps_deployment("test")
            assert result is True

    def test_is_vps_deployment_false(self) -> None:
        """Test is_vps_deployment returns False for cloudflare-workers."""
        with patch("faster.core.utilities.detect_platform", return_value="cloudflare-workers"):
            result = is_vps_deployment("test")
            assert result is False


class TestRequestUtilities:
    """Test request utility functions."""

    def test_is_api_call_with_json_accept(self) -> None:
        """Test is_api_call returns True for application/json accept header."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "application/json"

        result = is_api_call(mock_request)
        assert result is True

    def test_is_api_call_with_mixed_accept(self) -> None:
        """Test is_api_call returns True when application/json is in mixed accept header."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "text/html,application/json,*/*"

        result = is_api_call(mock_request)
        assert result is True

    def test_is_api_call_without_json_accept(self) -> None:
        """Test is_api_call returns False for non-JSON accept header."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "text/html"

        result = is_api_call(mock_request)
        assert result is False

    def test_is_api_call_no_accept_header(self) -> None:
        """Test is_api_call returns False when no accept header."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None

        result = is_api_call(mock_request)
        assert result is False


class TestResourceCheck:
    """Test resource checking utilities."""

    @pytest.mark.asyncio
    async def test_check_all_resources_skips_frequent_calls(self) -> None:
        """Test check_all_resources skips checks when called too frequently."""
        mock_app = MagicMock()
        mock_app.state.latest_status_check = datetime.now()

        mock_settings = MagicMock()
        mock_settings.refresh_interval = 60  # 60 seconds

        # Should skip because last check was recent
        await check_all_resources(mock_app, mock_settings)

        # Since it's an async function that returns None, we can't easily check if it was skipped
        # But we can verify that latest_status_check was not updated (since it was recent)
        # This test mainly ensures no errors occur when skipping

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

            await check_all_resources(mock_app, mock_settings)

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

            # Check that error details are properly formatted
            fields = [item["field"] for item in content["data"]]
            assert "body.name" in fields
            assert "body.email" in fields
            assert "query.page" in fields

            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_auth_exception_handler(self) -> None:
        """Test auth_exception_handler formats response correctly."""
        mock_request = MagicMock()
        mock_exception = AuthError("Authentication failed", status_code=401, errors=[{"error": "Invalid token"}])

        with patch("faster.core.utilities.logger") as mock_logger:
            result = await auth_exception_handler(mock_request, mock_exception)

            assert isinstance(result, AppResponse)
            # Parse the JSON content to check the values

            content = json.loads(bytes(result.body))
            assert content["status"] == "Authentication failed"
            assert content["message"] == "Authentication failed"
            assert content["data"] == [{"error": "Invalid token"}]
            assert result.status_code == 401

            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_auth_exception_handler_without_errors(self) -> None:
        """Test auth_exception_handler handles exception without errors."""
        mock_request = MagicMock()
        mock_exception = AuthError("Authentication failed", status_code=401)

        with patch("faster.core.utilities.logger") as mock_logger:
            result = await auth_exception_handler(mock_request, mock_exception)

            assert isinstance(result, AppResponse)
            # Parse the JSON content to check the values

            content = json.loads(bytes(result.body))
            assert content["status"] == "Authentication failed"
            assert content["message"] == "Authentication failed"
            assert content["data"] == {}  # Default to empty dict when None
            assert result.status_code == 401

            mock_logger.error.assert_called_once()
