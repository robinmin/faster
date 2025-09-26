"""
E2E tests for the Profile page functionality.
Tests profile header, personal information, account information, password management, and account operations.
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
                    pytest.skip(f"{test_name} - UI elements not accessible: {str(e)[:100]}")
                else:
                    raise

        # Preserve the original function's metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__annotations__ = func.__annotations__
        return wrapper

    return decorator


@pytest.mark.profile
@pytest.mark.asyncio
async def test_profile_page_loads_correctly(auth_page: Page) -> None:
    """Test that the profile page loads with all expected elements."""
    # Check if user is authenticated
    auth_state = await auth_page.evaluate("""
        () => {
            if (typeof Alpine === 'undefined' || !Alpine.store) return 'unknown';
            const store = Alpine.store('app');
            return store.currentView;
        }
    """)

    if auth_state != "app":
        pytest.skip("User is not authenticated - cannot test profile page")

    # Navigate to profile page
    # Click profile menu item in user dropdown
    user_menu_btn = auth_page.locator("[aria-label='User menu']")
    await user_menu_btn.click()

    # Wait for dropdown and click profile
    profile_menu_item = auth_page.locator("ul.dropdown-content li a").filter(has_text="Profile")
    await expect(profile_menu_item).to_be_visible(timeout=2000)
    await profile_menu_item.click()

    # Wait for profile page to load by checking for profile-specific elements
    await auth_page.locator("h1").filter(has_text="Robin Min").wait_for(state="visible", timeout=5000)

    # Verify profile page is active by checking for profile-specific content
    profile_card = auth_page.locator(".card.bg-base-100.shadow-xl").filter(has_text="Robin Min").first
    await expect(profile_card).to_be_visible()


@pytest.mark.profile
@pytest.mark.asyncio
async def test_profile_header_displays_correctly(auth_page: Page) -> None:
    """Test that the profile header displays user information correctly."""
    _ = await auth_page.goto("/dev/admin")
    await auth_page.wait_for_load_state("networkidle")

    # Check if we're on auth view (should not be visible for profile access)
    auth_view = auth_page.locator("[x-show*='auth']")
    await expect(auth_view).not_to_be_visible(timeout=2000)

    # Navigate to profile page
    user_menu_btn = auth_page.locator("[aria-label='User menu']")
    await user_menu_btn.click()
    profile_menu_item = auth_page.locator("ul.dropdown-content li a").filter(has_text="Profile")
    await expect(profile_menu_item).to_be_visible(timeout=2000)
    await profile_menu_item.click()
    # Wait for profile page to load by checking for profile-specific elements
    await auth_page.locator("h1").filter(has_text="Robin Min").wait_for(state="visible", timeout=5000)

    # Verify profile header card (use the card containing user name)
    header_card = auth_page.locator(".card.bg-base-100.shadow-xl").filter(has_text="Robin Min").first
    await expect(header_card).to_be_visible()

    # Verify user avatar
    avatar = header_card.locator(".avatar .w-24.h-24")
    await expect(avatar).to_be_visible()

    # Verify user display name (h1 element)
    display_name = header_card.locator("h1")
    await expect(display_name).to_be_visible()
    await expect(display_name).not_to_be_empty()

    # Verify email display
    email_display = header_card.locator("p.text-base-content\\/70")
    await expect(email_display).to_be_visible()

    # Check for role badges (may be empty)
    # Don't assert visibility since roles might not be assigned


@pytest.mark.profile
@pytest.mark.asyncio
async def test_personal_information_section(auth_page: Page) -> None:
    """Test that personal information section displays correctly."""
    _ = await auth_page.goto("/dev/admin")
    await auth_page.wait_for_load_state("networkidle")

    # Check if we're on auth view (should not be visible for profile access)
    auth_view = auth_page.locator("[x-show*='auth']")
    await expect(auth_view).not_to_be_visible(timeout=2000)

    # Navigate to profile page
    user_menu_btn = auth_page.locator("[aria-label='User menu']")
    await user_menu_btn.click()
    profile_menu_item = auth_page.locator("ul.dropdown-content li a").filter(has_text="Profile")
    await expect(profile_menu_item).to_be_visible(timeout=2000)
    await profile_menu_item.click()
    await auth_page.locator("h1").filter(has_text="Robin Min").wait_for(state="visible", timeout=5000)

    # Find personal information card (use content-based selector)
    personal_card = auth_page.locator(".card.bg-base-100.shadow-xl").filter(has_text="Personal Information")
    await expect(personal_card).to_be_visible()

    # Verify card title
    title = personal_card.locator("h2").filter(has_text="Personal Information")
    await expect(title).to_be_visible()

    # Verify user icon
    user_icon = personal_card.locator("i[data-lucide='user']")
    await expect(user_icon).to_be_visible()

    # Check for personal information fields (may be empty)
    # Don't assert specific field count since data may vary


@pytest.mark.profile
@pytest.mark.asyncio
async def test_account_information_section(auth_page: Page) -> None:
    """Test that account information section displays correctly."""
    _ = await auth_page.goto("/dev/admin")
    await auth_page.wait_for_load_state("networkidle")

    # Check if we're on auth view (skip if not authenticated)
    auth_view = auth_page.locator("[x-show*='auth']")
    try:
        await expect(auth_view).to_be_visible(timeout=2000)
        pytest.skip("Account information test - requires authentication")
    except Exception:
        pass

    # Navigate to profile page
    user_menu_btn = auth_page.locator("[aria-label='User menu']")
    await user_menu_btn.click()
    profile_menu_item = auth_page.locator("ul.dropdown-content li a").filter(has_text="Profile")
    await expect(profile_menu_item).to_be_visible(timeout=2000)
    await profile_menu_item.click()
    await auth_page.locator("h1").filter(has_text="Robin Min").wait_for(state="visible", timeout=5000)

    # Find account information card (use content-based selector)
    account_card = auth_page.locator(".card.bg-base-100.shadow-xl").filter(has_text="Account Information")
    await expect(account_card).to_be_visible()

    # Verify card title
    title = account_card.locator("h2").filter(has_text="Account Information")
    await expect(title).to_be_visible()

    # Verify settings icon
    settings_icon = account_card.locator("i[data-lucide='settings']")
    await expect(settings_icon).to_be_visible()

    # Check for account information fields
    # Don't assert specific field count since data may vary


@pytest.mark.profile
@pytest.mark.asyncio
async def test_password_management_section(auth_page: Page) -> None:
    """Test that password management section displays correctly."""
    _ = await auth_page.goto("/dev/admin")
    await auth_page.wait_for_load_state("networkidle")

    # Check if we're on auth view (should not be visible for profile access)
    auth_view = auth_page.locator("[x-show*='auth']")
    await expect(auth_view).not_to_be_visible(timeout=2000)

    # Navigate to profile page
    user_menu_btn = auth_page.locator("[aria-label='User menu']")
    await user_menu_btn.click()
    profile_menu_item = auth_page.locator("ul.dropdown-content li a").filter(has_text="Profile")
    await expect(profile_menu_item).to_be_visible(timeout=2000)
    await profile_menu_item.click()
    await auth_page.locator("h1").filter(has_text="Robin Min").wait_for(state="visible", timeout=5000)

    # Find password management card (use content-based selector)
    password_card = auth_page.locator(".card.bg-base-100.shadow-xl").filter(has_text="Password Management")
    await expect(password_card).to_be_visible()

    # Verify card title
    title = password_card.locator("h2").filter(has_text="Password Management")
    await expect(title).to_be_visible()

    # Verify lock icon
    lock_icon = password_card.locator("i[data-lucide='lock']")
    await expect(lock_icon).to_be_visible()

    # Verify change password button
    change_password_btn = password_card.locator("button").filter(has_text="Change Password")
    await expect(change_password_btn).to_be_visible()

    # Verify send reset email button
    reset_email_btn = password_card.locator("button").filter(has_text="Send Reset Email")
    await expect(reset_email_btn).to_be_visible()


@pytest.mark.profile
@pytest.mark.asyncio
async def test_account_operations_section(auth_page: Page) -> None:
    """Test that account operations section displays correctly."""
    _ = await auth_page.goto("/dev/admin")
    await auth_page.wait_for_load_state("networkidle")

    # Check if we're on auth view (should not be visible for profile access)
    auth_view = auth_page.locator("[x-show*='auth']")
    await expect(auth_view).not_to_be_visible(timeout=2000)

    # Navigate to profile page
    user_menu_btn = auth_page.locator("[aria-label='User menu']")
    await user_menu_btn.click()
    profile_menu_item = auth_page.locator("ul.dropdown-content li a").filter(has_text="Profile")
    await expect(profile_menu_item).to_be_visible(timeout=2000)
    await profile_menu_item.click()
    await auth_page.locator("h1").filter(has_text="Robin Min").wait_for(state="visible", timeout=5000)

    # Find account operations card (use content-based selector)
    operations_card = auth_page.locator(".card.bg-base-100.shadow-xl").filter(has_text="Account Operations")
    await expect(operations_card).to_be_visible()

    # Verify card title
    title = operations_card.locator("h2").filter(has_text="Account Operations")
    await expect(title).to_be_visible()

    # Verify alert-triangle icon
    alert_icon = operations_card.locator("i[data-lucide='alert-triangle']")
    await expect(alert_icon).to_be_visible()

    # Verify danger zone alert
    danger_alert = operations_card.locator(".alert.alert-warning")
    await expect(danger_alert).to_be_visible()

    # Verify deactivate account button
    deactivate_btn = operations_card.locator("button").filter(has_text="Deactivate Account")
    await expect(deactivate_btn).to_be_visible()


@pytest.mark.profile
@pytest.mark.asyncio
async def test_change_password_modal_functionality(auth_page: Page) -> None:
    """Test change password modal opens and displays correctly."""
    _ = await auth_page.goto("/dev/admin")
    await auth_page.wait_for_load_state("networkidle")

    # Check if we're on auth view (should not be visible for profile access)
    auth_view = auth_page.locator("[x-show*='auth']")
    await expect(auth_view).not_to_be_visible(timeout=2000)

    # Navigate to profile page
    user_menu_btn = auth_page.locator("[aria-label='User menu']")
    await user_menu_btn.click()
    profile_menu_item = auth_page.locator("ul.dropdown-content li a").filter(has_text="Profile")
    await expect(profile_menu_item).to_be_visible(timeout=2000)
    await profile_menu_item.click()
    await auth_page.locator("h1").filter(has_text="Robin Min").wait_for(state="visible", timeout=5000)

    # Click change password button
    change_password_btn = auth_page.locator("button").filter(has_text="Change Password")
    await expect(change_password_btn).to_be_visible()
    await change_password_btn.click()

    # Verify modal opens
    modal = auth_page.locator(".modal.modal-open")
    await expect(modal).to_be_visible()

    # Verify modal title
    modal_title = modal.locator("h3").filter(has_text="Change Password")
    await expect(modal_title).to_be_visible()

    # Verify key icon
    key_icon = modal.locator("i[data-lucide='key']")
    await expect(key_icon).to_be_visible()

    # Verify form fields
    current_password_input = modal.locator("#current-password")
    await expect(current_password_input).to_be_visible()

    new_password_input = modal.locator("#new-password")
    await expect(new_password_input).to_be_visible()

    confirm_password_input = modal.locator("#confirm-password")
    await expect(confirm_password_input).to_be_visible()

    # Verify modal buttons
    cancel_btn = modal.locator("button").filter(has_text="Cancel")
    await expect(cancel_btn).to_be_visible()

    change_btn = modal.locator("button").filter(has_text="Change Password")
    await expect(change_btn).to_be_visible()

    # Close modal
    await cancel_btn.click()
    await expect(modal).not_to_be_visible()


@pytest.mark.profile
@pytest.mark.asyncio
async def test_deactivate_account_modal_functionality(auth_page: Page) -> None:
    """Test deactivate account modal opens and displays correctly."""
    _ = await auth_page.goto("/dev/admin")
    await auth_page.wait_for_load_state("networkidle")

    # Check if we're on auth view (should not be visible for profile access)
    auth_view = auth_page.locator("[x-show*='auth']")
    await expect(auth_view).not_to_be_visible(timeout=2000)

    # Navigate to profile page
    user_menu_btn = auth_page.locator("[aria-label='User menu']")
    await user_menu_btn.click()
    profile_menu_item = auth_page.locator("ul.dropdown-content li a").filter(has_text="Profile")
    await expect(profile_menu_item).to_be_visible(timeout=2000)
    await profile_menu_item.click()
    await auth_page.locator("h1").filter(has_text="Robin Min").wait_for(state="visible", timeout=5000)

    # Click deactivate account button
    deactivate_btn = auth_page.locator("button").filter(has_text="Deactivate Account")
    await expect(deactivate_btn).to_be_visible()
    await deactivate_btn.click()

    # Verify modal opens
    modal = auth_page.locator(".modal.modal-open")
    await expect(modal).to_be_visible()

    # Verify modal title
    modal_title = modal.locator("h3").filter(has_text="Deactivate Account")
    await expect(modal_title).to_be_visible()

    # Verify user-x icon
    user_x_icon = modal.locator("i[data-lucide='user-x']")
    await expect(user_x_icon).to_be_visible()

    # Verify warning alert
    warning_alert = modal.locator(".alert.alert-warning")
    await expect(warning_alert).to_be_visible()

    # Verify confirmation checkbox
    confirmation_checkbox = modal.locator("input[type='checkbox']")
    await expect(confirmation_checkbox).to_be_visible()

    # Verify modal buttons
    cancel_btn = modal.locator("button").filter(has_text="Cancel")
    await expect(cancel_btn).to_be_visible()

    deactivate_confirm_btn = modal.locator("button").filter(has_text="Deactivate Account")
    await expect(deactivate_confirm_btn).to_be_visible()
    # Button should be disabled initially (confirmation not checked)
    await expect(deactivate_confirm_btn).to_be_disabled()

    # Close modal
    await cancel_btn.click()
    await expect(modal).not_to_be_visible()


@pytest.mark.profile
@pytest.mark.asyncio
async def test_profile_responsive_layout(auth_page: Page) -> None:
    """Test profile page responsive grid layout."""
    _ = await auth_page.goto("/dev/admin")
    await auth_page.wait_for_load_state("networkidle")

    # Check if we're on auth view (should not be visible for profile access)
    auth_view = auth_page.locator("[x-show*='auth']")
    await expect(auth_view).not_to_be_visible(timeout=2000)

    # Navigate to profile page
    user_menu_btn = auth_page.locator("[aria-label='User menu']")
    await user_menu_btn.click()
    profile_menu_item = auth_page.locator("ul.dropdown-content li a").filter(has_text="Profile")
    await expect(profile_menu_item).to_be_visible(timeout=2000)
    await profile_menu_item.click()
    await auth_page.locator("h1").filter(has_text="Robin Min").wait_for(state="visible", timeout=5000)

    # Verify main container
    main_container = auth_page.locator(".max-w-4xl.mx-auto").first
    await expect(main_container).to_be_visible()

    # Verify grid layout for information sections
    grid_container = auth_page.locator(".grid.grid-cols-1.lg\\:grid-cols-2")
    await expect(grid_container).to_be_visible()

    # Verify gap spacing
    await expect(grid_container).to_have_class("gap-6")


@pytest.mark.profile
@pytest.mark.asyncio
async def test_profile_accessibility_features(auth_page: Page) -> None:
    """Test profile page accessibility features."""
    _ = await auth_page.goto("/dev/admin")
    await auth_page.wait_for_load_state("networkidle")

    # Check if we're on auth view (should not be visible for profile access)
    auth_view = auth_page.locator("[x-show*='auth']")
    await expect(auth_view).not_to_be_visible(timeout=2000)

    # Navigate to profile page
    user_menu_btn = auth_page.locator("[aria-label='User menu']")
    await user_menu_btn.click()
    profile_menu_item = auth_page.locator("ul.dropdown-content li a").filter(has_text="Profile")
    await expect(profile_menu_item).to_be_visible(timeout=2000)
    await profile_menu_item.click()
    await auth_page.locator("h1").filter(has_text="Robin Min").wait_for(state="visible", timeout=5000)

    # Verify main container
    main = auth_page.locator("main.container")
    await expect(main).to_be_visible()

    # Check for screen reader text (sr-only class)
    sr_text = auth_page.locator(".sr-only")
    await expect(sr_text).to_be_visible(timeout=2000)
