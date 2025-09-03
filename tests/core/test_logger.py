from unittest.mock import MagicMock, patch

from structlog.types import EventDict

from faster.core.logger import (
    add_cid,
    console_renderer,
    file_renderer,
    get_logger,
    setup_logger,
)


class TestAddCID:
    """Test cases for add_cid function."""

    @patch("faster.core.logger.correlation_id")
    def test_add_cid_with_correlation_id(self, mock_correlation_id: MagicMock) -> None:
        """Test add_cid with correlation ID present."""
        mock_correlation_id.get.return_value = "test-correlation-id-12345"

        event_dict: EventDict = {"event": "test message", "level": "info"}

        result = add_cid(None, "test", event_dict)

        assert result["correlation_id"] == "test-correlation-id-12345"
        assert result["cid"] == "test-cor"  # First 8 chars (default length)
        assert result["event"] == "test message"
        assert result["level"] == "info"

    @patch("faster.core.logger.correlation_id")
    def test_add_cid_without_correlation_id(self, mock_correlation_id: MagicMock) -> None:
        """Test add_cid without correlation ID."""
        mock_correlation_id.get.return_value = None

        event_dict: EventDict = {"event": "test message", "level": "info"}

        result = add_cid(None, "test", event_dict)

        assert result["cid"] == ""
        assert "correlation_id" not in result
        assert result["event"] == "test message"
        assert result["level"] == "info"

    @patch("faster.core.logger.correlation_id")
    def test_add_cid_preserves_existing_fields(self, mock_correlation_id: MagicMock) -> None:
        """Test add_cid preserves existing fields."""
        mock_correlation_id.get.return_value = "test-id"

        event_dict: EventDict = {"event": "test message", "level": "info", "existing_field": "existing_value"}

        result = add_cid(None, "test", event_dict)

        assert result["correlation_id"] == "test-id"
        assert result["cid"] == "test-id"
        assert result["existing_field"] == "existing_value"


class TestConsoleRenderer:
    """Test cases for console renderer functions."""

    def test_console_renderer_returns_callable(self) -> None:
        """Test console_renderer returns a callable."""
        renderer = console_renderer()
        assert callable(renderer)

    @patch("faster.core.logger._default_config")
    def test_console_renderer_with_timestamp_and_cid(self, mock_config: MagicMock) -> None:
        """Test console renderer with timestamp and correlation ID."""
        mock_config.__getitem__.return_value.__getitem__.return_value = True

        event_dict: EventDict = {
            "timestamp": "2023-10-05T14:48:00.123456Z",
            "level": "INFO",
            "cid": "test-cid-123",
            "logger": "test.logger",
            "event": "Test message",
        }

        renderer = console_renderer()
        result = renderer(None, "test", event_dict)

        assert "14:48:00.123" in result  # trimmed timestamp
        assert "INFO" in result  # log level should be present
        assert "[test-cid-123]" in result
        assert "[test.logger]" in result
        assert "Test message" in result

    @patch("faster.core.logger._default_config")
    def test_console_renderer_without_logger_name(self, mock_config: MagicMock) -> None:
        """Test console renderer without logger name when disabled."""
        mock_config.__getitem__.return_value.__getitem__.return_value = False

        event_dict: EventDict = {
            "timestamp": "2023-10-05T14:48:00.123456Z",
            "level": "INFO",
            "cid": "test-cid",
            "logger": "test.logger",
            "event": "Test message",
        }

        renderer = console_renderer()
        result = renderer(None, "test", event_dict)

        assert "[test.logger]" not in result

    @patch("faster.core.logger._default_config")
    def test_console_renderer_with_color_enabled(self, mock_config: MagicMock) -> None:
        """Test console renderer with color enabled."""
        mock_config.__getitem__.return_value.__getitem__.return_value = True

        event_dict: EventDict = {"timestamp": "2023-10-05T14:48:00.123456Z", "level": "ERROR", "event": "Error message"}

        renderer = console_renderer()
        result = renderer(None, "test", event_dict)

        # Should contain ANSI color codes for ERROR level
        assert "\033[31m" in result  # Red color for ERROR
        assert "\033[0m" in result  # Reset code

    @patch("faster.core.logger._default_config")
    def test_console_renderer_with_color_disabled(self, mock_config: MagicMock) -> None:
        """Test console renderer with color disabled."""
        mock_config.__getitem__.return_value.__getitem__.return_value = False

        event_dict: EventDict = {"timestamp": "2023-10-05T14:48:00.123456Z", "level": "ERROR", "event": "Error message"}

        renderer = console_renderer()
        result = renderer(None, "test", event_dict)

        # Should not contain ANSI color codes
        assert "\033[" not in result

    def test_console_renderer_without_timestamp(self) -> None:
        """Test console renderer without timestamp."""
        event_dict: EventDict = {"level": "INFO", "event": "Test message"}

        renderer = console_renderer()
        result = renderer(None, "test", event_dict)

        assert "Test message" in result
        assert "INFO" in result  # log level should be present

    def test_console_renderer_with_empty_cid(self) -> None:
        """Test console renderer with empty correlation ID."""
        event_dict: EventDict = {"level": "INFO", "cid": "", "event": "Test message"}

        renderer = console_renderer()
        result = renderer(None, "test", event_dict)

        assert "[]" not in result  # No empty brackets for empty CID


class TestFileRenderer:
    """Test cases for file renderer functions."""

    def test_file_renderer_returns_callable(self) -> None:
        """Test file_renderer returns a callable."""
        renderer = file_renderer()
        assert callable(renderer)

    @patch("faster.core.logger._default_config")
    def test_file_renderer_with_timestamp_and_cid(self, mock_config: MagicMock) -> None:
        """Test file renderer with timestamp and correlation ID."""
        mock_config.__getitem__.return_value.__getitem__.return_value = True

        event_dict: EventDict = {
            "timestamp": "2023-10-05T14:48:00.123456Z",
            "level": "INFO",
            "correlation_id": "full-correlation-id-12345",
            "logger": "test.logger",
            "event": "Test message",
            "extra_field": "extra_value",
        }

        renderer = file_renderer()
        result = renderer(None, "test", event_dict)

        assert "2023-10-05T14:48:00.123456Z" in result  # full timestamp
        assert "INFO" in result  # log level should be present
        assert "[full-correlation-id-12345]" in result
        assert "[test.logger]" in result
        assert "Test message" in result
        assert "extra_value" in result

    @patch("faster.core.logger._default_config")
    def test_file_renderer_without_logger_name(self, mock_config: MagicMock) -> None:
        """Test file renderer without logger name when disabled."""
        mock_config.__getitem__.return_value.__getitem__.return_value = False

        event_dict: EventDict = {
            "timestamp": "2023-10-05T14:48:00.123456Z",
            "level": "INFO",
            "event": "Test message",
            "logger": "test.logger",
        }

        renderer = file_renderer()
        result = renderer(None, "test", event_dict)

        assert "[test.logger]" not in result

    def test_file_renderer_without_timestamp(self) -> None:
        """Test file renderer without timestamp."""
        event_dict: EventDict = {"level": "INFO", "event": "Test message"}

        renderer = file_renderer()
        result = renderer(None, "test", event_dict)

        assert "Test message" in result
        assert "INFO" in result  # log level should be present

    def test_file_renderer_without_cid(self) -> None:
        """Test file renderer without correlation ID."""
        event_dict: EventDict = {"level": "INFO", "event": "Test message"}

        renderer = file_renderer()
        result = renderer(None, "test", event_dict)

        assert "[]" not in result  # No empty brackets


class TestSetupLogger:
    """Test cases for setup_logger function."""

    @patch("faster.core.logger.logging")
    @patch("faster.core.logger.structlog")
    @patch("faster.core.logger.sys")
    @patch("faster.core.logger._merge_dict")
    def test_setup_logger_basic_config(
        self, mock_merge_dict: MagicMock, mock_sys: MagicMock, mock_structlog: MagicMock, mock_logging: MagicMock
    ) -> None:
        """Test setup_logger with basic configuration."""
        # Mock the merged config result
        mock_merge_dict.return_value = {
            "console": {
                "enabled": True,
                "correlation_id_length": 8,
                "show_logger_name": False,
                "colorize_level": True,
            },
            "file": {
                "enabled": False,  # Disable file logging for this test
                "format": "json",
                "path": "logs/app.log",
                "encoding": "utf-8",
                "mode": "a",
            },
            "external_loggers": {
                "propagate": ["uvicorn", "uvicorn.error", "uvicorn.access"],
                "ignore": ["aiosqlite", "sentry_sdk.errors"],
            },
        }

        mock_root_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_root_logger

        setup_logger()

        # Verify root logger setup - setLevel may be called multiple times for external loggers
        assert mock_root_logger.setLevel.called
        # handlers.clear is called for root logger + external loggers
        assert mock_root_logger.handlers.clear.call_count >= 1

        # Verify console handler setup
        mock_logging.StreamHandler.assert_called_once()
        # The call should be with sys.stdout (which is mocked)
        call_args = mock_logging.StreamHandler.call_args
        assert call_args is not None

        # Verify structlog configuration
        mock_structlog.configure.assert_called_once()

    @patch("faster.core.logger.logging")
    @patch("faster.core.logger.structlog")
    @patch("faster.core.logger.sys")
    @patch("faster.core.logger._merge_dict")
    def test_setup_logger_debug_mode(
        self, mock_merge_dict: MagicMock, mock_sys: MagicMock, mock_structlog: MagicMock, mock_logging: MagicMock
    ) -> None:
        """Test setup_logger in debug mode."""
        # Mock the merged config result
        mock_merge_dict.return_value = {
            "console": {
                "enabled": True,
                "correlation_id_length": 8,
                "show_logger_name": False,
                "colorize_level": True,
            },
            "file": {
                "enabled": False,  # Disable file logging for this test
                "format": "json",
                "path": "logs/app.log",
                "encoding": "utf-8",
                "mode": "a",
            },
            "external_loggers": {
                "propagate": ["uvicorn", "uvicorn.error", "uvicorn.access"],
                "ignore": ["aiosqlite", "sentry_sdk.errors"],
            },
        }

        mock_root_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_root_logger

        setup_logger(is_debug=True)

        # Verify debug level is set
        assert mock_root_logger.setLevel.called

    @patch("faster.core.logger.logging")
    @patch("faster.core.logger.structlog")
    @patch("faster.core.logger.sys")
    @patch("faster.core.logger._merge_dict")
    def test_setup_logger_custom_log_level(
        self, mock_merge_dict: MagicMock, mock_sys: MagicMock, mock_structlog: MagicMock, mock_logging: MagicMock
    ) -> None:
        """Test setup_logger with custom log level."""
        # Mock the merged config result
        mock_merge_dict.return_value = {
            "console": {
                "enabled": True,
                "correlation_id_length": 8,
                "show_logger_name": False,
                "colorize_level": True,
            },
            "file": {
                "enabled": False,  # Disable file logging for this test
                "format": "json",
                "path": "logs/app.log",
                "encoding": "utf-8",
                "mode": "a",
            },
            "external_loggers": {
                "propagate": ["uvicorn", "uvicorn.error", "uvicorn.access"],
                "ignore": ["aiosqlite", "sentry_sdk.errors"],
            },
        }

        mock_root_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_root_logger

        setup_logger(log_level="WARNING")

        # Verify custom level is set - may be called multiple times for external loggers
        assert mock_root_logger.setLevel.call_count >= 1

    @patch("faster.core.logger.logging")
    @patch("faster.core.logger.structlog")
    @patch("faster.core.logger.sys")
    @patch("faster.core.logger._merge_dict")
    def test_setup_logger_with_file_output(
        self, mock_merge_dict: MagicMock, mock_sys: MagicMock, mock_structlog: MagicMock, mock_logging: MagicMock
    ) -> None:
        """Test setup_logger with file output enabled."""
        # Mock the merged config result
        mock_merge_dict.return_value = {
            "console": {
                "enabled": True,
                "correlation_id_length": 8,
                "show_logger_name": False,
                "colorize_level": True,
            },
            "file": {
                "enabled": True,  # Enable file logging for this test
                "format": "json",
                "path": "logs/app.log",
                "encoding": "utf-8",
                "mode": "a",
            },
            "external_loggers": {
                "propagate": ["uvicorn", "uvicorn.error", "uvicorn.access"],
                "ignore": ["aiosqlite", "sentry_sdk.errors"],
            },
        }

        mock_root_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_root_logger

        setup_logger(log_file="/tmp/test.log")

        # Verify file handler is created
        mock_logging.FileHandler.assert_called_once()

    @patch("faster.core.logger.logging")
    @patch("faster.core.logger.structlog")
    @patch("faster.core.logger.sys")
    @patch("faster.core.logger._merge_dict")
    def test_setup_logger_json_format(
        self, mock_merge_dict: MagicMock, mock_sys: MagicMock, mock_structlog: MagicMock, mock_logging: MagicMock
    ) -> None:
        """Test setup_logger with JSON format."""
        # Mock the merged config result
        mock_merge_dict.return_value = {
            "console": {
                "enabled": True,
                "correlation_id_length": 8,
                "show_logger_name": False,
                "colorize_level": True,
            },
            "file": {
                "enabled": True,  # Enable file logging for this test
                "format": "json",
                "path": "logs/app.log",
                "encoding": "utf-8",
                "mode": "a",
            },
            "external_loggers": {
                "propagate": ["uvicorn", "uvicorn.error", "uvicorn.access"],
                "ignore": ["aiosqlite", "sentry_sdk.errors"],
            },
        }

        mock_root_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_root_logger

        setup_logger(log_format="json")

        # Verify JSON renderer is used for file output
        mock_structlog.processors.JSONRenderer.assert_called_once()


class TestGetLogger:
    """Test cases for get_logger function."""

    @patch("faster.core.logger.structlog.get_logger")
    def test_get_logger(self, mock_structlog_get_logger: MagicMock) -> None:
        """Test get_logger function."""
        mock_logger = MagicMock()
        mock_structlog_get_logger.return_value = mock_logger

        result = get_logger("test.logger")

        assert result == mock_logger
        mock_structlog_get_logger.assert_called_once_with("test.logger")


class TestLoggerIntegration:
    """Integration tests for logger functionality."""

    @patch("faster.core.logger.logging")
    @patch("faster.core.logger.structlog")
    @patch("faster.core.logger.sys")
    def test_logger_setup_creates_handlers(
        self, mock_sys: MagicMock, mock_structlog: MagicMock, mock_logging: MagicMock
    ) -> None:
        """Test that logger setup creates the expected handlers."""
        mock_root_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_root_logger

        setup_logger()

        # Verify handlers are added to root logger
        mock_root_logger.addHandler.assert_called()

    @patch("faster.core.logger.structlog.get_logger")
    def test_get_logger_integration(self, mock_structlog_get_logger: MagicMock) -> None:
        """Test get_logger returns a properly configured logger."""
        mock_logger = MagicMock()
        mock_structlog_get_logger.return_value = mock_logger

        logger = get_logger("my.app.module")

        assert logger is not None
        mock_structlog_get_logger.assert_called_with("my.app.module")
