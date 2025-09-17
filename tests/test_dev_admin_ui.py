"""UI tests for Dev Admin Dashboard HTML structure."""

from pathlib import Path

import pytest


@pytest.fixture
def html_content() -> str:
    """Load the HTML content from the dev-admin.html file."""
    current_dir = Path(__file__).parent
    parent_dir = current_dir.parent
    html_path = parent_dir / "faster" / "resources" / "dev-admin.html"

    with open(html_path, encoding="utf-8") as f:
        return f.read()


def test_html_structure_basic(html_content: str) -> None:
    """Test basic HTML structure."""
    # Check title
    assert "<title>Dev Admin Dashboard</title>" in html_content

    # Check that Alpine.js is included
    assert "https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" in html_content

    # Check that DaisyUI is included
    assert "https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css" in html_content


def test_navigation_menu_structure(html_content: str) -> None:
    """Test that navigation menu has all required items."""
    # Check that all menu items are defined in the userMenu function
    menu_items = ["Dashboard", "Onboarding", "Profile", "User Management", "Sys Health", "App State", "Request State"]
    for item in menu_items:
        assert f'label: "{item}"' in html_content


def test_profile_page_structure(html_content: str) -> None:
    """Test that Profile page has correct structure."""
    # Check for main sections
    assert "Personal Information" in html_content
    assert "Account Information" in html_content
    assert "Password Management" in html_content
    assert "Account Operations" in html_content


def test_password_management_buttons(html_content: str) -> None:
    """Test that password management buttons are present."""
    # Check for password management buttons
    assert "Change Password" in html_content
    assert "Send Reset Email" in html_content


def test_account_operations_buttons(html_content: str) -> None:
    """Test that account operations buttons are present."""
    # Check for account operations buttons
    assert "Deactivate Account" in html_content


def test_user_management_page_structure(html_content: str) -> None:
    """Test that User Management page has correct structure."""
    # Check for main sections
    assert "User Management" in html_content
    assert "User Lookup" in html_content
    assert "Target User ID" in html_content


def test_user_management_buttons(html_content: str) -> None:
    """Test that user management action buttons are present."""
    # Check for action buttons (updated to reflect new UI)
    buttons = ["Ban User", "Unban User", "Adjust Roles", "View Basic Info"]
    for button_text in buttons:
        assert button_text in html_content, f"Button '{button_text}' not found"


def test_modals_structure(html_content: str) -> None:
    """Test that required modals are present."""
    # Check for password change modal
    assert 'x-if="showPasswordChangeModal"' in html_content

    # Check for deactivate account modal
    assert 'x-if="showDeactivateModal"' in html_content

    # Check for user management modals (updated to reflect new modals)
    assert 'x-if="showAdjustRolesModal"' in html_content
    assert 'x-if="showBanConfirmModal"' in html_content
    assert 'x-if="showUnbanConfirmModal"' in html_content


def test_javascript_functions_present(html_content: str) -> None:
    """Test that required JavaScript functions are defined."""
    # Check for profile page functions
    required_functions = [
        "changePassword()",
        "initiatePasswordReset()",
        "deactivateAccount()",
        "userManagementPage()",
        "banUser()",
        "unbanUser()",
        "adjustRoles()",
        "viewUserBasicInfo()",
        "openAdjustRolesModal()",
    ]

    for func in required_functions:
        assert func in html_content, f"Function '{func}' not found in JavaScript"


def test_theme_toggle_present(html_content: str) -> None:
    """Test that theme toggle functionality is present."""
    # Check for theme toggle button
    assert 'title="Toggle theme"' in html_content

    # Check that theme toggle component exists
    assert "themeToggle()" in html_content


def test_responsive_classes(html_content: str) -> None:
    """Test that responsive CSS classes are used."""
    # Check for responsive grid classes
    responsive_classes = ["md:grid-cols-2", "lg:grid-cols-3", "md:flex-row", "lg:grid-cols-4"]

    for cls in responsive_classes:
        assert cls in html_content, f"Responsive class '{cls}' not found"
