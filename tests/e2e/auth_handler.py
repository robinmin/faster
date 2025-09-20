"""
Authentication handler for E2E tests with Supabase and Google OAuth.
Manages session caching and refresh for Playwright tests.
"""

import json
from pathlib import Path
import time
from typing import Any, cast

from playwright.async_api import Page


class SupabaseAuthHandler:
    """Handles Supabase authentication for E2E tests."""

    def __init__(self, auth_file_path: str = "./tests/e2e/playwright-auth.json"):
        self.auth_file_path = Path(auth_file_path)
        self.session_data: dict[str, Any] | None = None

    async def load_cached_session(self) -> dict[str, Any] | None:
        """Load cached session from JSON file."""
        if not self.auth_file_path.exists():
            return None

        try:
            with open(self.auth_file_path) as f:
                session_data = cast(dict[str, Any], json.load(f))

            # Check if session is expired
            if self._is_session_expired(session_data):
                return None

            return session_data
        except Exception as e:
            print(f"Error loading cached session: {e}")
            return None

    def _is_session_expired(self, session_data: dict[str, Any]) -> bool:
        """Check if the session is expired."""
        if not session_data.get("supabase_session"):
            return True

        session = session_data["supabase_session"]
        expires_at = session.get("expires_at")

        if not expires_at:
            return True

        # Add 5 minute buffer before actual expiration
        return time.time() >= (cast(float, expires_at) - 300)

    async def save_session(self, session_data: dict[str, Any]) -> None:
        """Save session data to JSON file."""
        try:
            self.auth_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.auth_file_path, "w") as f:
                json.dump(session_data, f, indent=2)
        except Exception as e:
            print(f"Error saving session: {e}")

    async def perform_google_oauth_login(self, page: Page) -> dict[str, Any]:
        """
        Perform Google OAuth login and capture session data.
        This requires manual intervention for the Google login flow.
        """
        print("🔐 Starting Google OAuth login flow...")

        # Navigate to your app's login page
        _ = await page.goto("http://127.0.0.1:8000/dev/admin")

        # Wait for the page to load
        await page.wait_for_load_state("networkidle")

        # Look for Google sign-in button (adjust selector based on your UI)
        google_login_button = page.locator(
            'button:has-text("Google"), button:has-text("Sign in with Google"), [data-provider="google"]'
        )

        if await google_login_button.count() > 0:
            print("📱 Found Google login button, clicking...")
            await google_login_button.first.click()
        else:
            print("⚠️  Google login button not found. Please manually trigger OAuth login.")
            _ = input("Press Enter after you've initiated the Google OAuth flow...")

        # Wait for OAuth popup or redirect
        print("🌐 Waiting for Google OAuth flow to complete...")
        print("👤 Please complete the Google OAuth login manually in the browser.")
        print("🔄 The test will continue once authentication is complete...")

        # Wait for successful authentication (adjust condition based on your app)
        try:
            # Wait for either:
            # 1. Redirect to dashboard/authenticated page
            # 2. Presence of authenticated user indicator
            # 3. localStorage to contain session data

            _ = await page.wait_for_function(
                """
                () => {
                    // Check if localStorage has Supabase session
                    const session = localStorage.getItem('sb-' + window.location.host.replace(/[^a-zA-Z0-9]/g, '') + '-auth-token');
                    if (session) {
                        try {
                            const parsed = JSON.parse(session);
                            return parsed && parsed.access_token;
                        } catch (e) {
                            return false;
                        }
                    }

                    // Alternative: check for auth state in the app
                    return window.location.pathname.includes('dashboard') ||
                           document.querySelector('[data-authenticated="true"]') ||
                           document.querySelector('.user-profile');
                }
                """,
                timeout=120000,  # 2 minutes timeout
            )

            print("✅ Authentication completed successfully!")

        except Exception as e:
            print(f"⚠️  Timeout waiting for authentication completion: {e}")
            print("🔄 Continuing anyway - please ensure you're logged in...")

        # Extract session data from localStorage
        session_data = await self._extract_session_data(page)

        if session_data:
            await self.save_session(session_data)
            print("💾 Session data saved successfully!")
        else:
            print("⚠️  Failed to extract session data")

        return session_data or {}

    async def _extract_session_data(self, page: Page) -> dict[str, Any] | None:
        """Extract Supabase session data from the page."""
        try:
            # Get localStorage data
            local_storage = cast(
                dict[str, Any],
                await page.evaluate("""
                () => {
                    const storage = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        if (key && key.includes('supabase') || key.includes('sb-')) {
                            storage[key] = localStorage.getItem(key);
                        }
                    }
                    return storage;
                }
            """),
            )

            # Get cookies
            cookies = await page.context.cookies()

            # Extract Supabase session specifically
            supabase_session = cast(
                dict[str, Any] | None,
                await page.evaluate("""
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
            """),
            )

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

    async def apply_session_to_page(self, page: Page, session_data: dict[str, Any]) -> bool:
        """Apply cached session data to the page."""
        try:
            # Set localStorage data
            if session_data.get("local_storage"):
                for key, value in session_data["local_storage"].items():
                    await page.evaluate(f"localStorage.setItem('{key}', {json.dumps(value)})")

            # Set cookies
            if session_data.get("cookies"):
                await page.context.add_cookies(session_data["cookies"])

            # Optionally set Supabase session directly if your app supports it
            if session_data.get("supabase_session"):
                await page.evaluate(f"""
                    () => {{
                        window.supabaseSession = {json.dumps(session_data["supabase_session"])};

                        // Trigger session restoration in your app if needed
                        if (window.restoreSupabaseSession) {{
                            window.restoreSupabaseSession(window.supabaseSession);
                        }}
                    }}
                """)

            return True

        except Exception as e:
            print(f"Error applying session to page: {e}")
            return False

    async def refresh_session_if_needed(self, page: Page) -> bool:
        """Check if session needs refresh and handle it."""
        try:
            # Check current session validity
            is_valid = await page.evaluate("""
                async () => {
                    // Check if Supabase client is available and session is valid
                    if (window.supabase && window.supabase.auth) {
                        const { data: { session }, error } = await window.supabase.auth.getSession();
                        return session && !error;
                    }
                    return false;
                }
            """)

            if not is_valid:
                print("🔄 Session invalid, attempting refresh...")

                # Try to refresh the session
                refreshed = await page.evaluate("""
                    async () => {
                        if (window.supabase && window.supabase.auth) {
                            const { data, error } = await window.supabase.auth.refreshSession();
                            return data.session && !error;
                        }
                        return false;
                    }
                """)

                if refreshed:
                    print("✅ Session refreshed successfully!")
                    # Save the new session
                    session_data = await self._extract_session_data(page)
                    if session_data:
                        await self.save_session(session_data)
                    return True
                print("❌ Session refresh failed")
                return False

            return True

        except Exception as e:
            print(f"Error refreshing session: {e}")
            return False


class AuthenticatedPage:
    """Context manager for pages with authentication."""

    def __init__(self, auth_handler: SupabaseAuthHandler, page: Page):
        self.auth_handler = auth_handler
        self.page = page

    async def __aenter__(self) -> Page:
        """Setup authenticated page."""
        # Load cached session
        session_data = await self.auth_handler.load_cached_session()

        if session_data:
            print("📋 Using cached session...")
            success = await self.auth_handler.apply_session_to_page(self.page, session_data)
            if success and await self.auth_handler.refresh_session_if_needed(self.page):
                return self.page

        print("🔐 No valid cached session, performing login...")
        _ = await self.auth_handler.perform_google_oauth_login(self.page)
        return self.page

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Cleanup."""
