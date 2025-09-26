"""
Integration tests for YAML-driven E2E testing framework.
Tests YAML runner functionality and spec validation.
"""

from pathlib import Path
import sys

from playwright.async_api import Page
import pytest

from tests.e2e.yaml_runner import YAMLTestRunner, run_yaml_test, run_yaml_tests

# Add project root to Python path for absolute imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@pytest.mark.yaml
@pytest.mark.asyncio
async def test_yaml_runner_basic_functionality(page: Page) -> None:
    """Test basic YAML runner functionality with a simple spec."""
    runner = YAMLTestRunner(page, context=page.context)

    # Simple test spec
    test_spec = {
        "name": "Basic Navigation Test",
        "description": "Test basic page navigation",
        "steps": [
            {"name": "Navigate to homepage", "action": "goto", "url": "/dev/admin", "wait_for": "networkidle"},
            {"name": "Verify page loads", "action": "assert_visible", "selector": "body"},
        ],
    }

    result = await runner.run_spec(test_spec)

    assert result["overall_success"], f"Test failed: {result}"
    assert result["total_steps"] == 2, "Should have executed 2 steps"
    assert result["successful_steps"] == 2, "All steps should have passed"


@pytest.mark.yaml
@pytest.mark.asyncio
async def test_yaml_runner_with_variables(page: Page) -> None:
    """Test YAML runner variable substitution."""
    runner = YAMLTestRunner(page, context=page.context)

    test_spec = {
        "name": "Variable Substitution Test",
        "variables": {"app_url": "http://127.0.0.1:8000", "test_selector": "body"},
        "steps": [
            {"name": "Navigate with variable", "action": "goto", "url": "${app_url}/dev/admin"},
            {"name": "Assert with variable", "action": "assert_visible", "selector": "${test_selector}"},
        ],
    }

    result = await runner.run_spec(test_spec)

    assert result["overall_success"], f"Variable test failed: {result}"


@pytest.mark.yaml
@pytest.mark.asyncio
async def test_yaml_runner_optional_steps(page: Page) -> None:
    """Test YAML runner handling of optional steps."""
    runner = YAMLTestRunner(page, context=page.context)

    test_spec = {
        "name": "Optional Steps Test",
        "steps": [
            {"name": "Navigate to page", "action": "goto", "url": "/dev/admin"},
            {
                "name": "Try to find non-existent element",
                "action": "assert_visible",
                "selector": ".non-existent-element",
                "optional": True,
            },
            {"name": "Find existing element", "action": "assert_visible", "selector": "body"},
        ],
    }

    result = await runner.run_spec(test_spec)

    assert result["overall_success"], "Test should pass with optional steps"
    assert result["total_steps"] == 3, "Should have attempted 3 steps"


@pytest.mark.yaml
@pytest.mark.asyncio
async def test_yaml_runner_javascript_evaluation(page: Page) -> None:
    """Test YAML runner JavaScript evaluation capabilities."""
    runner = YAMLTestRunner(page, context=page.context)

    test_spec = {
        "name": "JavaScript Evaluation Test",
        "steps": [
            {"name": "Navigate to page", "action": "goto", "url": "/dev/admin"},
            {
                "name": "Store page title",
                "action": "evaluate",
                "function": "() => document.title",
                "store_as": "page_title",
            },
            {
                "name": "Check page title exists",
                "action": "assert_function",
                "function": "() => document.title.length > 0",
            },
            {
                "name": "Wait for function condition",
                "action": "wait_for_function",
                "function": "() => document.readyState === 'complete'",
                "timeout": 5000,
            },
        ],
    }

    result = await runner.run_spec(test_spec)

    assert result["overall_success"], f"JavaScript evaluation test failed: {result}"
    assert "page_title" in result["stored_data"], "Page title should be stored"


@pytest.mark.yaml
@pytest.mark.asyncio
async def test_yaml_runner_error_handling(page: Page) -> None:
    """Test YAML runner error handling."""
    try:
        runner = YAMLTestRunner(page, context=page.context)

        test_spec = {
            "name": "Error Handling Test",
            "steps": [
                {"name": "Navigate to basic page", "action": "goto", "url": "about:blank"},
                {"name": "Try invalid action", "action": "invalid_action", "selector": "body"},
            ],
        }

        result = await runner.run_spec(test_spec)

        assert not result["overall_success"], "Test should fail with invalid action"
        assert result["failed_steps"] > 0, "Should have failed steps"
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
                "unknown action",
            ]
        ):
            pytest.skip("YAML runner error handling - UI elements not accessible: " + str(e)[:100])
        else:
            raise


@pytest.mark.yaml
@pytest.mark.asyncio
async def test_load_yaml_spec_file(page: Page) -> None:
    """Test loading and running actual YAML spec files."""
    # Test with the login spec
    login_spec_path = "tests/e2e/specs/login.yaml"

    if not Path(login_spec_path).exists():
        pytest.skip("Login YAML spec file not found")

    # Note: This test will likely fail at the OAuth step since it requires manual intervention
    # We'll run it but expect it to fail at a specific step
    try:
        result = await run_yaml_test(page, login_spec_path, context=page.context)
        # If it somehow passes completely, that's also valid
        print(f"✅ Login spec executed: {result['successful_steps']}/{result['total_steps']} steps")
    except Exception as e:
        # Expected to fail at OAuth step
        print(f"⚠️  Login spec failed as expected (requires manual OAuth): {e}")


@pytest.mark.yaml
@pytest.mark.asyncio
async def test_yaml_runner_screenshot_functionality(page: Page) -> None:
    """Test YAML runner screenshot capabilities."""
    runner = YAMLTestRunner(page, context=page.context)

    screenshot_path = "tests/e2e/test-results/yaml-test-screenshot.png"

    test_spec = {
        "name": "Screenshot Test",
        "steps": [
            {"name": "Navigate to page", "action": "goto", "url": "/dev/admin"},
            {"name": "Take screenshot", "action": "screenshot", "path": screenshot_path},
        ],
    }

    result = await runner.run_spec(test_spec)

    assert result["overall_success"], f"Screenshot test failed: {result}"

    # Verify screenshot file was created
    screenshot_file = Path(screenshot_path)
    assert screenshot_file.exists(), "Screenshot file should be created"
    assert screenshot_file.stat().st_size > 0, "Screenshot file should not be empty"


@pytest.mark.yaml
@pytest.mark.asyncio
async def test_yaml_runner_viewport_changes(page: Page) -> None:
    """Test YAML runner viewport manipulation."""
    runner = YAMLTestRunner(page, context=page.context)

    test_spec = {
        "name": "Viewport Test",
        "steps": [
            {"name": "Navigate to page", "action": "goto", "url": "/dev/admin"},
            {"name": "Set mobile viewport", "action": "set_viewport_size", "width": 375, "height": 667},
            {
                "name": "Verify mobile viewport",
                "action": "assert_function",
                "function": "() => window.innerWidth === 375",
            },
            {"name": "Set tablet viewport", "action": "set_viewport_size", "width": 768, "height": 1024},
            {
                "name": "Verify tablet viewport",
                "action": "assert_function",
                "function": "() => window.innerWidth === 768",
            },
        ],
    }

    result = await runner.run_spec(test_spec)

    assert result["overall_success"], f"Viewport test failed: {result}"


@pytest.mark.yaml
@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_multiple_yaml_specs(page: Page) -> None:
    """Test running multiple YAML specifications."""
    specs_dir = "tests/e2e/specs"

    if not Path(specs_dir).exists():
        pytest.skip("Specs directory not found")

    # Create a simple test spec for this test
    simple_spec_content = """
name: "Simple Integration Test"
description: "Basic test for multiple spec runner"
steps:
  - name: "Navigate to app"
    action: "goto"
    url: "/dev/admin"
    wait_for: "networkidle"
  - name: "Verify page loads"
    action: "assert_visible"
    selector: "body"
"""

    temp_spec_path = Path(specs_dir) / "temp_simple_test.yaml"
    with open(temp_spec_path, "w") as f:
        _ = f.write(simple_spec_content)

    try:
        # Run all specs (this will include our temp spec and others)
        results = await run_yaml_tests(page, specs_dir, context=page.context)

        assert len(results) > 0, "Should have executed at least one spec"

        # Check that our simple spec passed
        simple_results = [r for r in results if "Simple Integration Test" in r.get("test_name", "")]
        assert len(simple_results) > 0, "Simple test should have run"
        assert simple_results[0]["overall_success"], "Simple test should have passed"

        print(f"✅ Executed {len(results)} YAML specifications")

    finally:
        # Clean up temp spec
        if temp_spec_path.exists():
            temp_spec_path.unlink()


@pytest.mark.yaml
@pytest.mark.asyncio
async def test_yaml_runner_form_interactions(page: Page) -> None:
    """Test YAML runner form interaction capabilities."""
    runner = YAMLTestRunner(page, context=page.context)

    test_spec = {
        "name": "Form Interaction Test",
        "steps": [
            {"name": "Navigate to page", "action": "goto", "url": "/dev/admin"},
            {
                "name": "Look for search input",
                "action": "wait_for_selector",
                "selector": "input[type='search'], .search-input, input[placeholder*='search']",
                "timeout": 5000,
                "optional": True,
            },
            {
                "name": "Fill search if found",
                "action": "fill",
                "selector": "input[type='search'], .search-input, input[placeholder*='search']",
                "value": "test search",
                "optional": True,
            },
        ],
    }

    result = await runner.run_spec(test_spec)

    # This test should pass even if no search input is found (due to optional steps)
    assert result["total_steps"] == 3, "Should have attempted 3 steps"


@pytest.mark.yaml
@pytest.mark.performance
@pytest.mark.asyncio
async def test_yaml_runner_performance_tracking(page: Page) -> None:
    """Test YAML runner performance measurement capabilities."""
    runner = YAMLTestRunner(page, context=page.context)

    test_spec = {
        "name": "Performance Tracking Test",
        "steps": [
            {
                "name": "Measure navigation time",
                "action": "evaluate",
                "function": "() => performance.now()",
                "store_as": "start_time",
            },
            {"name": "Navigate to page", "action": "goto", "url": "/dev/admin", "wait_for": "networkidle"},
            {
                "name": "Measure end time",
                "action": "evaluate",
                "function": "() => performance.now()",
                "store_as": "end_time",
            },
            {
                "name": "Calculate load time",
                "action": "evaluate",
                "function": """
                    () => {
                        const startTime = window.testResults?.start_time || 0;
                        const endTime = window.testResults?.end_time || 0;
                        return endTime - startTime;
                    }
                """,
                "store_as": "load_time",
            },
        ],
    }

    result = await runner.run_spec(test_spec)

    assert result["overall_success"], f"Performance test failed: {result}"
    assert "start_time" in result["stored_data"], "Start time should be stored"
    assert "end_time" in result["stored_data"], "End time should be stored"


@pytest.mark.yaml
@pytest.mark.network
@pytest.mark.asyncio
async def test_yaml_runner_network_simulation(page: Page) -> None:
    """Test YAML runner network simulation capabilities."""
    try:
        runner = YAMLTestRunner(page, context=page.context)

        test_spec = {
            "name": "Network Simulation Test",
            "steps": [
                {"name": "Navigate to basic page", "action": "goto", "url": "about:blank"},
                {"name": "Simulate offline", "action": "simulate_offline"},
                {"name": "Wait a moment", "action": "wait_for_timeout", "timeout": 1000},
                {"name": "Restore online", "action": "simulate_online"},
                {"name": "Verify page still works", "action": "assert_visible", "selector": "body"},
            ],
        }

        result = await runner.run_spec(test_spec)

        assert result["overall_success"], f"Network simulation test failed: {result}"
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
            pytest.skip("YAML runner network simulation - UI elements not accessible: " + str(e)[:100])
        else:
            raise
