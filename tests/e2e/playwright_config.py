"""
Playwright configuration in Python.
Replaces playwright.config.js with a Python-based configuration.
"""

from pathlib import Path
from typing import Any, ClassVar, cast


class PlaywrightConfig:
    """Playwright configuration settings."""

    BASE_URL = "http://127.0.0.1:8000"
    TIMEOUT = 30000
    AUTH_FILE = "./tests/e2e/playwright-auth.json"

    # Browser configurations
    BROWSERS: ClassVar[dict[str, Any]] = {
        "chromium": {
            "name": "chromium",
            "launch_options": {
                "channel": "chrome",
                "headless": False,  # Set to True for CI/CD
                "args": [
                    "--disable-blink-features=AutomationControlled",  # Key flag for Gmail
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-extensions",
                ],
            },
            "context_options": {
                "viewport": {"width": 1280, "height": 720},
                "ignore_https_errors": True,
                "record_video_dir": "./tests/e2e/videos",
                "record_video_size": {"width": 1280, "height": 720},
            },
        },
        "firefox": {
            "name": "firefox",
            "launch_options": {
                "headless": False,
            },
            "context_options": {
                "viewport": {"width": 1280, "height": 720},
                "record_video_dir": "./tests/e2e/videos",
                "record_video_size": {"width": 1280, "height": 720},
            },
        },
        "webkit": {
            "name": "webkit",
            "launch_options": {
                "headless": False,
            },
            "context_options": {
                "viewport": {"width": 1280, "height": 720},
                "record_video_dir": "./tests/e2e/videos",
                "record_video_size": {"width": 1280, "height": 720},
            },
        },
    }

    # Mobile device configurations
    MOBILE_DEVICES: ClassVar[dict[str, Any]] = {
        "mobile_chrome": {
            "name": "Mobile Chrome",
            "use": {
                "viewport": {"width": 375, "height": 667},
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "has_touch": True,
                "is_mobile": True,
            },
        },
        "mobile_safari": {
            "name": "Mobile Safari",
            "use": {
                "viewport": {"width": 375, "height": 812},
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "has_touch": True,
                "is_mobile": True,
            },
        },
    }

    @classmethod
    def get_browser_config(cls, browser_name: str, headless: bool | None = None) -> dict[str, Any]:
        """Get configuration for a specific browser."""
        config = cls.BROWSERS.get(browser_name, cls.BROWSERS["chromium"]).copy()

        # Override headless mode if specified
        if headless is not None:
            config["launch_options"]["headless"] = headless

        # Add common settings to context options
        if "context_options" not in config:
            config["context_options"] = {}

        config["context_options"].update(
            {
                "base_url": cls.BASE_URL,
            }
        )

        return cast(dict[str, Any], config)

    @classmethod
    def get_headless_config(cls, browser_name: str = "chromium") -> dict[str, Any]:
        """Get headless configuration for automated testing."""
        return cls.get_browser_config(browser_name, headless=True)

    @classmethod
    def get_mobile_config(cls, device_name: str) -> dict[str, Any]:
        """Get configuration for a mobile device."""
        config = cls.MOBILE_DEVICES.get(device_name, cls.MOBILE_DEVICES["mobile_chrome"]).copy()

        # Add common settings
        config["use"].update(
            {
                "baseURL": cls.BASE_URL,
                "actionTimeout": cls.TIMEOUT,
                "navigationTimeout": cls.TIMEOUT,
            }
        )

        return cast(dict[str, Any], config)

    @classmethod
    def get_test_dirs(cls) -> dict[str, Path]:
        """Get test directory paths."""
        base_dir = Path(__file__).parent
        return {
            "results": base_dir / "test-results",
            "screenshots": base_dir / "screenshots",
            "videos": base_dir / "videos",
            "traces": base_dir / "traces",
            "specs": base_dir / "specs",
        }

    @classmethod
    def ensure_directories(cls) -> None:
        """Ensure all required directories exist."""
        dirs = cls.get_test_dirs()
        for dir_path in dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)
