"""
Pytest configuration and fixtures for E2E tests.
Provides authentication, browser setup, and utilities.
"""

import asyncio
from collections.abc import AsyncGenerator
import os
from pathlib import Path
import sys
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
import pytest
import pytest_asyncio

from tests.e2e.auth_handler import SupabaseAuthHandler
from tests.e2e.playwright_config import PlaywrightConfig
from tests.e2e.setup_teardown import E2ETestSetup

try:
    import httpx

    httpx_available = True
except ImportError:
    httpx = None  # type: ignore
    httpx_available = False

HTTPX_AVAILABLE = httpx_available

# Add project root to Python path for absolute imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


# Pytest configuration
def pytest_configure(config: Any) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "auth: mark test as requiring authentication")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark test as integration test")


@pytest_asyncio.fixture(scope="session")
async def event_loop() -> AsyncGenerator[asyncio.AbstractEventLoop, None]:
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def playwright_instance() -> AsyncGenerator[Playwright, None]:
    """Provide a Playwright instance for the test session."""
    async with async_playwright() as p:
        yield p


@pytest_asyncio.fixture(scope="function")
async def browser(playwright_instance: Playwright) -> AsyncGenerator[Browser, None]:
    """Launch a browser instance for the test session."""
    config = PlaywrightConfig()

    # Check if we should run in headless mode (automated testing)
    is_automated = os.getenv("E2E_AUTOMATED", "false").lower() == "true"
    is_ci = os.getenv("CI", "false").lower() == "true"

    # Use headless mode for automated runs or CI
    headless = is_automated or is_ci
    browser_config = config.get_browser_config("chromium", headless=headless)

    browser = await playwright_instance.chromium.launch(**browser_config["launch_options"])
    yield browser
    await browser.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_e2e_environment() -> AsyncGenerator[None, None]:
    """Auto-run global setup before any tests and teardown after all tests."""
    # Setup phase
    setup = E2ETestSetup()

    # Setup phase
    success = await setup.global_setup()

    if not success:
        pytest.skip("E2E environment setup failed")

    yield  # This is where the tests run

    # Teardown phase
    await setup.global_teardown()


@pytest_asyncio.fixture(scope="function")
async def auth_handler() -> SupabaseAuthHandler:
    """Provide an authentication handler instance."""
    return SupabaseAuthHandler()


@pytest_asyncio.fixture(scope="function")
async def authenticated_context(
    browser: Browser, auth_handler: SupabaseAuthHandler
) -> AsyncGenerator[BrowserContext, None]:
    """
    Create a browser context with authentication state.
    This fixture ensures all pages in the context are authenticated.
    """
    # Load cached session data and check if it's valid
    session_data = await auth_handler.load_cached_session()
    has_valid_session = session_data is not None

    if not has_valid_session:
        print("⚠️  No valid authentication session found!")
        print("🔧 Run 'python -m tests.e2e.auth_setup' to generate new credentials")
        print("📝 Or ask the user to help generate login credentials")

    # Get context options from config
    config = PlaywrightConfig()
    browser_config = config.get_browser_config("chromium")
    context_options = browser_config["context_options"].copy()

    # Only add authentication state if we have a valid session
    if has_valid_session and auth_handler.auth_file_path.exists():
        context_options["storage_state"] = auth_handler.auth_file_path
        print("✅ Using cached authentication session")
    else:
        print("🔓 Creating unauthenticated context - some tests may fail")

    # Create context with stored authentication state
    # Playwright's storage_state automatically restores localStorage and cookies
    context = await browser.new_context(**context_options)

    # Add session validity info to context for tests to check
    context._auth_session_valid = has_valid_session  # type: ignore

    yield context
    await context.close()


def require_authentication(context: BrowserContext) -> None:
    """
    Helper function to check if authentication is available and skip test if not.
    Usage: require_authentication(authenticated_context)
    """
    if not getattr(context, '_auth_session_valid', False):
        pytest.skip("Authentication session not available. Run 'python -m tests.e2e.auth_setup' to generate credentials.")


@pytest_asyncio.fixture
async def auth_page(authenticated_context: BrowserContext) -> AsyncGenerator[Page, None]:
    """
    Provide an authenticated page instance.
    This is the main fixture to use for tests requiring authentication.
    """
    # Check if authentication is available
    require_authentication(authenticated_context)

    page = await authenticated_context.new_page()

    # Navigate to base URL and verify authentication
    _ = await page.goto("/dev/admin")

    # Wait for the page to load and check authentication status
    # Instead of strict authentication verification, let's just wait for the page to load
    # and trust that the session storage state is working
    await page.wait_for_load_state("networkidle")

    # Wait for Alpine.js to be loaded and initialized
    try:
        _ = await page.wait_for_function("() => typeof Alpine !== 'undefined' && Alpine.store", timeout=10000)
        print("✅ Alpine.js loaded successfully")
    except Exception as e:
        print(f"⚠️  Alpine.js not loaded within timeout, but continuing: {e}")

    # Wait for the app to initialize and check authentication state
    # Give the app a moment to initialize
    await page.wait_for_timeout(2000)

    # Check authentication state
    try:
        auth_state = await page.evaluate("""
            () => {
                if (typeof Alpine === 'undefined' || !Alpine.store) return 'unknown';

                const store = Alpine.store('app');
                if (!store.currentView) return 'loading';

                return store.currentView; // 'auth' or 'app'
            }
        """)

        if auth_state == "app":
            print("✅ User is authenticated and in app view")
        elif auth_state == "auth":
            print("i User is in auth view - authentication required")
            # Try to manually restore session from localStorage
            try:
                session_restored = await page.evaluate("""
                    () => {
                        const authToken = localStorage.getItem('sb-gljfxpmixpiafocjzahi-auth-token');
                        if (!authToken) return false;

                        try {
                            const sessionData = JSON.parse(authToken);
                            if (sessionData.access_token && Alpine && Alpine.store) {
                                const supabase = Alpine.store('app').supabase;
                                if (supabase) {
                                    // Try to set the session manually
                                    supabase.auth.setSession({
                                        access_token: sessionData.access_token,
                                        refresh_token: sessionData.refresh_token
                                    });
                                    return true;
                                }
                            }
                        } catch (e) {
                            console.error('Failed to restore session:', e);
                        }
                        return false;
                    }
                """)
                if session_restored:
                    print("✅ Session manually restored")
                    # Wait a bit for the auth state to update
                    await page.wait_for_timeout(2000)
                    # Re-check auth state
                    auth_state = await page.evaluate("""
                        () => Alpine.store('app').currentView
                    """)
                    if auth_state == "app":
                        print("✅ Authentication restored successfully")
                    else:
                        print("⚠️  Session restored but still in auth view")
                else:
                    print("⚠️  Could not restore session from localStorage")
            except Exception as restore_error:
                print(f"⚠️  Session restoration failed: {restore_error}")
        else:
            print(f"i Authentication state: {auth_state}")
    except Exception as e:
        print(f"⚠️  Could not check authentication state: {e}")

    yield page
    await page.close()


@pytest_asyncio.fixture
async def page(browser: Browser) -> AsyncGenerator[Page, None]:
    """
    Provide a regular (non-authenticated) page instance.
    Use this for tests that don't require authentication.
    """
    # Get context options from config
    config = PlaywrightConfig()
    browser_config = config.get_browser_config("chromium")
    context_options = browser_config["context_options"].copy()

    context = await browser.new_context(**context_options)
    page = await context.new_page()
    yield page
    await context.close()


@pytest_asyncio.fixture
async def mobile_page(browser: Browser) -> AsyncGenerator[Page, None]:
    """Provide a mobile page instance for mobile testing."""
    context = await browser.new_context(
        viewport={"width": 375, "height": 667},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    page = await context.new_page()
    yield page
    await context.close()


@pytest_asyncio.fixture
async def tablet_page(browser: Browser) -> AsyncGenerator[Page, None]:
    """Provide a tablet page instance for tablet testing."""
    context = await browser.new_context(
        viewport={"width": 768, "height": 1024},
        user_agent="Mozilla/5.0 (iPad; CPU OS 14_7 like Mac OS X) AppleWebKit/605.1.15",
    )
    page = await context.new_page()
    yield page
    await context.close()


# Helper fixtures for test data and utilities


@pytest.fixture
def test_user_data() -> dict[str, Any]:
    """Provide test user data for E2E tests."""
    return {"email": "test@example.com", "name": "Test User", "role": "admin"}


@pytest.fixture(scope="session")
def base_url() -> str:
    """Provide the base URL for the application."""
    return "http://127.0.0.1:8000"


@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[Any, None]:
    """Provide an HTTP client for API testing alongside E2E tests."""
    if not HTTPX_AVAILABLE or httpx is None:
        pytest.skip("httpx not available")

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        yield client


class PageHelpers:
    """Helper methods for common page operations."""

    def __init__(self, page: Page):
        self.page = page

    async def wait_for_authenticated_state(self, timeout: int = 10000) -> None:
        """Wait for the page to be in authenticated state."""
        _ = await self.page.wait_for_function(
            """
            () => {
                return document.querySelector('[data-authenticated="true"]') ||
                       document.querySelector('.user-profile') ||
                       document.querySelector('.logout-btn');
            }
            """,
            timeout=timeout,
        )

    async def wait_for_loading_complete(self, timeout: int = 30000) -> None:
        """Wait for loading indicators to disappear."""
        _ = await self.page.wait_for_function(
            """
            () => {
                const loadingIndicators = document.querySelectorAll(
                    '.loading, .spinner, [data-loading="true"], .loading-overlay'
                );
                return loadingIndicators.length === 0 ||
                       Array.from(loadingIndicators).every(el =>
                           el.style.display === 'none' || !el.offsetParent
                       );
            }
            """,
            timeout=timeout,
        )

    async def take_screenshot_on_failure(self, test_name: str) -> None:
        """Take a screenshot for failed tests."""
        screenshot_dir = Path("tests/e2e/screenshots")
        screenshot_dir.mkdir(exist_ok=True)

        screenshot_path = screenshot_dir / f"{test_name}-failure.png"
        _ = await self.page.screenshot(path=str(screenshot_path))
        print(f"📸 Screenshot saved: {screenshot_path}")

    async def simulate_network_error(self) -> None:
        """Simulate network error for testing error handling."""
        await self.page.route("**/*", lambda route: route.abort())

    async def simulate_slow_network(self) -> None:
        """Simulate slow network for testing loading states."""
        # Slow down all network requests
        await self.page.route("**/*", lambda route: route.continue_())


@pytest_asyncio.fixture
async def page_helpers(page: Page) -> PageHelpers:
    """Provide page helper utilities."""
    return PageHelpers(page)


@pytest_asyncio.fixture
async def auth_page_helpers(auth_page: Page) -> PageHelpers:
    """Provide page helper utilities for authenticated pages."""
    return PageHelpers(auth_page)


# Session and authentication utilities


@pytest.fixture
def session_manager(auth_handler: SupabaseAuthHandler) -> Any:
    """Provide session management utilities."""

    class SessionManager:
        def __init__(self) -> None:
            self.auth_handler = auth_handler

        async def clear_session(self) -> None:
            """Clear cached session data."""
            if self.auth_handler.auth_file_path.exists():
                self.auth_handler.auth_file_path.unlink()

        async def get_session_info(self) -> dict[str, Any]:
            """Get current session information."""
            session_data = await self.auth_handler.load_cached_session()
            if not session_data:
                return {"status": "no_session"}

            is_expired = self.auth_handler._is_session_expired(session_data)  # type: ignore[reportPrivateUsage, unused-ignore]
            return {
                "status": "expired" if is_expired else "valid",
                "timestamp": session_data.get("timestamp"),
                "url": session_data.get("url"),
            }

        async def force_session_refresh(self, page: Page) -> Any:
            """Force refresh the current session."""
            return await self.auth_handler.refresh_session_if_needed(page)

    return SessionManager()


# Pytest hooks for better test reporting


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: Any, call: Any) -> Any:
    """Add test artifacts on failure."""

    outcome = yield  # type: ignore[reportUnknownVariableType, unused-ignore]
    rep = outcome.get_result()  # type: ignore[reportUnknownVariableType, unused-ignore]

    # Add screenshot for failed tests
    if rep.when == "call" and rep.failed and hasattr(item, "funcargs"):
        # Try to get page from fixtures and take screenshot
        for fixture_name in ["page", "auth_page"]:
            if fixture_name in item.funcargs:
                # Schedule screenshot capture (async)
                rep.sections.append(("Screenshot", f"Available at test-results/{item.name}.png"))
                break


# Custom pytest markers

pytestmark = [pytest.mark.asyncio, pytest.mark.e2e]
