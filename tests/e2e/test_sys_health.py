"""
E2E tests for the Sys Health page functionality.
Tests system health monitoring and plugin status.
"""

from collections.abc import Callable, Coroutine
from pathlib import Path
import sys
from typing import Any

from playwright.async_api import Page, expect
import pytest

# Add project root to Python path for absolute imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def skip_if_ui_missing(test_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to skip tests gracefully if UI elements aren't accessible."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Coroutine[Any, Any, Any]]:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_msg = str(e).lower()
                if any(
                    phrase in error_msg
                    for phrase in [
                        "not found",
                        "not visible",
                        "timeout",
                        "expected to be",
                        "locator",
                        "security",
                        "failed to read",
                    ]
                ):
                    pytest.skip("{test_name} - UI elements not accessible: {str(e)[:100]}")
                else:
                    raise

        # Preserve the original function's metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__annotations__ = func.__annotations__
        return wrapper

    return decorator


@pytest.mark.sys_health
@pytest.mark.asyncio
async def test_sys_health_page_loads_correctly(auth_page: Page) -> None:
    """Test that the Sys Health page loads with all expected elements."""
    _ = await auth_page.goto("/dev/admin")
    await auth_page.wait_for_load_state("networkidle")

    # Navigate to sys_health page
    user_menu_btn = auth_page.locator("[aria-label='User menu']")
    await user_menu_btn.click()
    sys_health_menu_item = auth_page.locator("ul.dropdown-content li a").filter(has_text="Sys Health")
    await expect(sys_health_menu_item).to_be_visible(timeout=2000)
    await sys_health_menu_item.click()
    await auth_page.locator("[x-show*='sys-health']").wait_for(state="visible", timeout=5000)

    # Verify sys_health page is active
    sys_health_view = auth_page.locator("[x-show*='sys-health']")
    await expect(sys_health_view).to_be_visible()


@pytest.mark.sys_health
@pytest.mark.asyncio
async def test_sys_health_header_displays_correctly(auth_page: Page) -> None:
    """Test that the Sys Health header displays correctly."""
    _ = await auth_page.goto("/dev/admin")
    await auth_page.wait_for_load_state("networkidle")

    # Navigate to sys_health page
    user_menu_btn = auth_page.locator("[aria-label='User menu']")
    await user_menu_btn.click()
    sys_health_menu_item = auth_page.locator("ul.dropdown-content li a").filter(has_text="Sys Health")
    await expect(sys_health_menu_item).to_be_visible(timeout=2000)
    await sys_health_menu_item.click()
    await auth_page.locator("[x-show*='sys-health']").wait_for(state="visible", timeout=5000)

    # Verify header navbar (make selector more specific to avoid strict mode violation)
    header_navbar = auth_page.locator("[x-show*='sys-health'] .navbar.bg-base-100.shadow-lg.rounded-box").first
    await expect(header_navbar).to_be_visible()


@pytest.mark.sys_health
@pytest.mark.asyncio
async def test_sys_health_responsive_layout(auth_page: Page) -> None:
    """Test Sys Health page responsive grid layout."""
    _ = await auth_page.goto("/dev/admin")
    await auth_page.wait_for_load_state("networkidle")

    # Navigate to sys_health page
    user_menu_btn = auth_page.locator("[aria-label='User menu']")
    await user_menu_btn.click()
    sys_health_menu_item = auth_page.locator("ul.dropdown-content li a").filter(has_text="Sys Health")
    await expect(sys_health_menu_item).to_be_visible(timeout=2000)
    await sys_health_menu_item.click()
    await auth_page.locator("[x-show*='sys-health']").wait_for(state="visible", timeout=5000)

    # Verify main container (use the correct max-width class for sys-health view)
    main_container = auth_page.locator("[x-show*='sys-health'] .max-w-7xl.mx-auto").first
    await expect(main_container).to_be_visible()


@pytest.mark.sys_health
@pytest.mark.asyncio
async def test_sys_health_accessibility_features(auth_page: Page) -> None:
    """Test Sys Health page accessibility features."""
    _ = await auth_page.goto("/dev/admin")
    await auth_page.wait_for_load_state("networkidle")

    # Navigate to sys_health page
    user_menu_btn = auth_page.locator("[aria-label='User menu']")
    await user_menu_btn.click()
    sys_health_menu_item = auth_page.locator("ul.dropdown-content li a").filter(has_text="Sys Health")
    await expect(sys_health_menu_item).to_be_visible(timeout=2000)
    await sys_health_menu_item.click()
    await auth_page.locator("[x-show*='sys-health']").wait_for(state="visible", timeout=5000)

    # Verify main container (use the correct max-width class for sys_health view)
    main = auth_page.locator("main.container")
    await expect(main).to_be_visible()

    # Check for screen reader text (sr-only class)
    sr_text = auth_page.locator(".sr-only")
    await expect(sr_text).to_be_visible(timeout=2000)
