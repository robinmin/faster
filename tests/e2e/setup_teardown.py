"""
Global setup and teardown for E2E tests.
Replaces global-setup.js and global-teardown.js with Python implementation.
"""

import asyncio
import json
from pathlib import Path
import sys
import time
from typing import Any

from playwright.async_api import Page, async_playwright

from tests.e2e.auth_handler import SupabaseAuthHandler
from tests.e2e.playwright_config import PlaywrightConfig

# Add project root to Python path for absolute imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class E2ETestSetup:
    """Handles global setup and teardown for E2E tests."""

    def __init__(self) -> None:
        self.auth_handler = SupabaseAuthHandler()
        self.config = PlaywrightConfig()

    async def global_setup(self) -> bool:
        """
        Global setup that runs once before all tests.
        Handles authentication and environment preparation.
        """
        print("🚀 Starting global E2E test setup...")

        try:
            # Ensure required directories exist
            self.config.ensure_directories()

            # Check if we have a valid cached session
            session_data = await self.auth_handler.load_cached_session()

            if session_data and not self.auth_handler._is_session_expired(session_data):  # type: ignore[reportPrivateUsage, unused-ignore]
                print("✅ Valid cached session found, skipping auth setup")
                return True

            print("🔐 No valid session found, setting up authentication...")
            return await self._setup_authentication()

        except Exception as e:
            print(f"❌ Global setup failed: {e}")
            return False

    async def _setup_authentication(self) -> bool:
        """Setup authentication by performing Google OAuth login."""
        async with async_playwright() as p:
            # Launch browser for authentication
            browser = await p.chromium.launch(
                headless=False,  # Always run headful for manual OAuth
                channel="chrome",
                args=[
                    "--disable-blink-features=AutomationControlled",  # Key flag for Gmail
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-extensions",
                ],
            )

            context = await browser.new_context()
            page = await context.new_page()

            try:
                success = await self._perform_oauth_login(page)
                return success

            finally:
                await browser.close()

    async def _perform_oauth_login(self, page: Page) -> bool:
        """Perform Google OAuth login flow."""
        try:
            print("🔐 Starting Google OAuth login flow...")

            # Navigate to the application
            _ = await page.goto(f"{self.config.BASE_URL}/dev/admin")
            await page.wait_for_load_state("networkidle")

            # Look for Google login button
            google_login_selectors = [
                'button:has-text("Google")',
                'button:has-text("Sign in with Google")',
                '[data-provider="google"]',
                ".google-signin-btn",
                "#google-login",
            ]

            login_button = None
            for selector in google_login_selectors:
                button = page.locator(selector)
                if await button.count() > 0:
                    login_button = button.first
                    break

            if login_button:
                print("📱 Found Google login button, clicking...")
                await login_button.click()
            else:
                print("⚠️  Google login button not found. Please manually trigger OAuth login.")

            print("🌐 Waiting for Google OAuth flow to complete...")
            print("👤 Please complete the Google OAuth login manually in the browser.")
            print("🔄 The setup will continue once authentication is complete...")

            # Wait for successful authentication
            _ = await page.wait_for_function(
                """
                () => {
                    // Check if localStorage has Supabase session
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        if (key && key.includes('auth-token')) {
                            try {
                                const session = JSON.parse(localStorage.getItem(key));
                                return session && session.access_token;
                            } catch (e) {
                                continue;
                            }
                        }
                    }

                    // Alternative checks for authentication
                    return window.location.pathname.includes('dashboard') ||
                           document.querySelector('[data-authenticated="true"]') ||
                           document.querySelector('.user-profile') ||
                           document.querySelector('.logout-btn');
                }
                """,
                timeout=120000,  # 2 minutes timeout
            )

            print("✅ Authentication completed successfully!")

            # Extract and save session data
            session_data = await self._extract_session_data(page)

            if session_data:
                await self.auth_handler.save_session(session_data)
                print("💾 Session data saved successfully!")
                return True
            print("⚠️  Failed to extract session data")
            return False

        except Exception as e:
            print(f"❌ OAuth login failed: {e}")
            return False

    async def _extract_session_data(self, page: Page) -> dict[str, Any] | None:
        """Extract session data from the page."""
        try:
            # Get localStorage data
            local_storage = await page.evaluate("""
                () => {
                    const storage = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        if (key && (key.includes('supabase') || key.includes('sb-'))) {
                            storage[key] = localStorage.getItem(key);
                        }
                    }
                    return storage;
                }
            """)

            # Get cookies
            cookies = await page.context.cookies()

            # Extract Supabase session specifically
            supabase_session = await page.evaluate("""
                () => {
                    // Look for Supabase auth token in localStorage
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        if (key && key.includes('auth-token')) {
                            try {
                                return JSON.parse(localStorage.getItem(key));
                            } catch (e) {
                                continue;
                            }
                        }
                    }

                    // Alternative: if your app exposes session data globally
                    return window.supabaseSession || null;
                }
            """)

            return {
                "timestamp": time.time(),
                "local_storage": local_storage,
                "cookies": cookies,
                "supabase_session": supabase_session,
                "url": page.url,
            }

        except Exception as e:
            print(f"Error extracting session data: {e}")
            return None

    async def global_teardown(self) -> None:
        """
        Global teardown that runs once after all tests.
        Cleanup tasks and reporting.
        """
        print("🧹 Running global E2E test teardown...")

        try:
            # Clean up temporary files if needed
            # (Keep session cache for reuse)

            # Generate test summary if needed
            _ = self._generate_test_summary()

            print("✅ Global teardown completed")

        except Exception as e:
            print(f"⚠️  Error during teardown: {e}")

    def _generate_test_summary(self) -> dict[str, Any]:
        """Generate a summary of test execution."""
        dirs = self.config.get_test_dirs()

        summary = {
            "timestamp": time.time(),
            "results_dir": str(dirs["results"]),
            "screenshots": len(list(dirs["screenshots"].glob("*.png"))) if dirs["screenshots"].exists() else 0,
            "videos": len(list(dirs["videos"].glob("*.webm"))) if dirs["videos"].exists() else 0,
            "traces": len(list(dirs["traces"].glob("*.zip"))) if dirs["traces"].exists() else 0,
        }

        summary_file = dirs["results"] / "test-summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"📊 Test summary saved to: {summary_file}")
        return summary


# Convenience functions for pytest integration
async def pytest_global_setup() -> bool:
    """Pytest-compatible global setup function."""
    setup = E2ETestSetup()
    return await setup.global_setup()


async def pytest_global_teardown() -> None:
    """Pytest-compatible global teardown function."""
    setup = E2ETestSetup()
    await setup.global_teardown()


# Main execution for standalone use
if __name__ == "__main__":

    async def main() -> None:
        setup = E2ETestSetup()
        success = await setup.global_setup()
        if not success:
            sys.exit(1)

    asyncio.run(main())
