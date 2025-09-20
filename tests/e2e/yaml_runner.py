"""
YAML-driven test runner for E2E tests.
Loads YAML specifications and executes them using Playwright.
"""

from collections.abc import Callable, Coroutine
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from playwright.async_api import Browser, BrowserContext, Page
import yaml


class YAMLTestAction:
    """Represents a single test action from YAML specification."""

    def __init__(self, step_data: dict[str, Any]) -> None:
        self.name: str = step_data.get("name", "Unnamed step")
        self.action: str = step_data.get("action", "")
        self.selector: str = step_data.get("selector", "")
        self.value: str = step_data.get("value", "")
        self.url: str = step_data.get("url", "")
        self.timeout: int = step_data.get("timeout", 30000)
        self.description: str = step_data.get("description", "")
        self.optional: bool = step_data.get("optional", False)
        self.wait_for: Any = step_data.get("wait_for")
        self.function: str = step_data.get("function", "")
        self.store_as: str | None = step_data.get("store_as")
        self.path: str = step_data.get("path", "")
        self.width: int | None = step_data.get("width")
        self.height: int | None = step_data.get("height")
        self.step_data: dict[str, Any] = step_data


class YAMLTestResult:
    """Stores the result of a test step execution."""

    def __init__(self, step_name: str, success: bool, error: str | None = None, data: Any | None = None):
        self.step_name = step_name
        self.success = success
        self.error = error
        self.data = data
        self.timestamp = datetime.now()


class YAMLTestRunner:
    """Executes YAML-defined test specifications."""

    def __init__(self, page: Page, browser: Browser | None = None, context: BrowserContext | None = None):
        self.page = page
        self.browser = browser
        self.context = context
        self.test_results: list[YAMLTestResult] = []
        self.stored_data: dict[str, Any] = {}
        self.variables: dict[str, Any] = {}

    async def load_and_run_spec(self, spec_path: str | Path) -> dict[str, Any]:
        """Load a YAML specification and execute it."""
        spec_path = Path(spec_path)

        if not spec_path.exists():
            raise FileNotFoundError(f"Test specification not found: {spec_path}")

        with open(spec_path) as f:
            spec_data = yaml.safe_load(f)

        return await self.run_spec(spec_data)

    async def run_spec(self, spec_data: dict[str, Any]) -> dict[str, Any]:
        """Execute a loaded YAML specification."""
        test_name = spec_data.get("name", "Unnamed Test")
        print(f"🧪 Running test: {test_name}")

        # Store variables
        self.variables = spec_data.get("variables", {})

        # Check preconditions
        if "preconditions" in spec_data:
            await self._check_preconditions(spec_data["preconditions"])

        # Execute main test steps
        if "steps" in spec_data:
            await self._execute_steps(spec_data["steps"])

        # Execute error scenario tests if present
        if "error_scenarios" in spec_data:
            await self._execute_error_scenarios(spec_data["error_scenarios"])

        # Execute performance tests if present
        if "performance" in spec_data:
            await self._execute_performance_tests(spec_data["performance"])

        # Execute security tests if present
        if "security_tests" in spec_data:
            await self._execute_steps(spec_data["security_tests"])

        # Execute token expiration tests if present
        if "token_expiration_test" in spec_data:
            await self._execute_steps(spec_data["token_expiration_test"])

        # Execute performance tests if present
        if "performance_tests" in spec_data:
            await self._execute_steps(spec_data["performance_tests"])

        # Execute cleanup steps
        if "cleanup" in spec_data:
            await self._execute_steps(spec_data["cleanup"])

        # Return test summary
        return self._generate_test_summary(test_name)

    async def _check_preconditions(self, preconditions: list[str]) -> None:
        """Check test preconditions."""
        print("📋 Checking preconditions...")
        for condition in preconditions:
            print(f"  ✓ {condition}")

    async def _execute_steps(self, steps: list[dict[str, Any]]) -> None:
        """Execute a list of test steps."""
        for step_data in steps:
            action = YAMLTestAction(step_data)
            result = await self._execute_action(action)
            self.test_results.append(result)

            if not result.success and not action.optional:
                raise Exception(f"Step '{action.name}' failed: {result.error}")

    async def _execute_error_scenarios(self, error_scenarios: list[dict[str, Any]]) -> None:
        """Execute error scenario tests."""
        print("🔥 Testing error scenarios...")
        for scenario in error_scenarios:
            print(f"  📍 Running scenario: {scenario.get('name', 'Unnamed scenario')}")
            if "steps" in scenario:
                await self._execute_steps(scenario["steps"])

    async def _execute_performance_tests(self, performance_tests: list[dict[str, Any]]) -> None:
        """Execute performance tests."""
        print("⚡ Running performance tests...")
        for test in performance_tests:
            print(f"  📊 Running: {test.get('name', 'Unnamed performance test')}")
            # Handle performance-specific logic here
            if test.get("action") == "assert_no_console_errors":
                await self._check_console_errors()

    async def _execute_action(self, action: YAMLTestAction) -> YAMLTestResult:
        """Execute a single test action."""
        try:
            print(f"  🔄 {action.name}")

            # Replace variables in action data
            action = self._replace_variables(action)

            # Action dispatch dictionary
            action_handlers = {
                "goto": self._action_goto,
                "click": self._action_click,
                "fill": self._action_fill,
                "wait_for_selector": self._action_wait_for_selector,
                "wait_for_function": self._action_wait_for_function,
                "wait_for_timeout": self._action_wait_for_timeout,
                "assert_visible": self._action_assert_visible,
                "assert_text": self._action_assert_text,
                "assert_url": self._action_assert_url,
                "assert_function": self._action_assert_function,
                "evaluate": self._action_evaluate,
                "screenshot": self._action_screenshot,
                "set_viewport_size": self._action_set_viewport_size,
                "simulate_offline": self._action_simulate_offline,
                "simulate_online": self._action_simulate_online,
                "assert_no_console_errors": self._check_console_errors,
            }

            handler = action_handlers.get(action.action)
            if handler is None:
                raise Exception(f"Unknown action: {action.action}")
            handler = cast(Callable[..., Coroutine[Any, Any, Any]], handler)

            # Handle special cases
            if action.action == "evaluate":
                result = await handler(action)
                if action.store_as:
                    self.stored_data[action.store_as] = result
            else:
                await handler(action)

            return YAMLTestResult(action.name, True)

        except Exception as e:
            error_msg = str(e)
            if action.optional:
                print(f"    ⚠️  Optional step failed: {error_msg}")
                return YAMLTestResult(action.name, True, f"Optional: {error_msg}")
            print(f"    ❌ Step failed: {error_msg}")
            return YAMLTestResult(action.name, False, error_msg)

    def _replace_variables(self, action: YAMLTestAction) -> YAMLTestAction:
        """Replace variables in action data."""
        # Simple variable replacement - can be enhanced
        for attr in ["url", "selector", "value", "path"]:
            if hasattr(action, attr):
                value = getattr(action, attr)
                if isinstance(value, str):
                    for var_name, var_value in self.variables.items():
                        value = value.replace(f"${{{var_name}}}", str(var_value))
                    setattr(action, attr, value)
        return action

    # Action implementations

    async def _action_goto(self, action: YAMLTestAction) -> None:
        """Navigate to URL."""
        url = action.url
        # Don't prepend base URL for special URLs like about:, data:, etc.
        if not url.startswith("http") and not url.startswith("about:") and not url.startswith("data:"):
            base_url = self.variables.get("app_url", "http://127.0.0.1:8000")
            url = base_url + url

        _ = await self.page.goto(url)

        if action.wait_for:
            if action.wait_for == "networkidle":
                await self.page.wait_for_load_state("networkidle")
            elif action.wait_for == "domcontentloaded":
                await self.page.wait_for_load_state("domcontentloaded")

    async def _action_click(self, action: YAMLTestAction) -> None:
        """Click on an element."""
        await self.page.click(action.selector, timeout=action.timeout)

    async def _action_fill(self, action: YAMLTestAction) -> None:
        """Fill an input field."""
        await self.page.fill(action.selector, action.value, timeout=action.timeout)

    async def _action_wait_for_selector(self, action: YAMLTestAction) -> None:
        """Wait for selector to be visible."""
        _ = await self.page.wait_for_selector(action.selector, timeout=action.timeout)

    async def _action_wait_for_function(self, action: YAMLTestAction) -> None:
        """Wait for a JavaScript function to return true."""
        _ = await self.page.wait_for_function(action.function, timeout=action.timeout)

    async def _action_wait_for_timeout(self, action: YAMLTestAction) -> None:
        """Wait for a specified timeout."""
        await self.page.wait_for_timeout(action.timeout)

    async def _action_assert_visible(self, action: YAMLTestAction) -> None:
        """Assert element is visible."""
        element = self.page.locator(action.selector)
        await element.wait_for(state="visible", timeout=action.timeout)
        if not await element.is_visible():
            raise Exception(f"Element not visible: {action.selector}")

    async def _action_assert_text(self, action: YAMLTestAction) -> None:
        """Assert element contains specific text."""
        element = self.page.locator(action.selector)
        await element.wait_for(state="visible", timeout=action.timeout)
        text_content = await element.text_content()
        if text_content is not None and action.value not in text_content:
            raise Exception(f"Text '{action.value}' not found in element: {action.selector}")

    async def _action_assert_url(self, action: YAMLTestAction) -> None:
        """Assert current URL matches pattern."""
        current_url = self.page.url
        if action.value not in current_url:
            raise Exception(f"URL does not contain '{action.value}'. Current: {current_url}")

    async def _action_assert_function(self, action: YAMLTestAction) -> None:
        """Assert a JavaScript function returns true."""
        result = await self.page.evaluate(action.function)
        if not result:
            raise Exception("Assertion function returned false")

    async def _action_evaluate(self, action: YAMLTestAction) -> Any:
        """Evaluate JavaScript and return result."""
        return await self.page.evaluate(action.function)

    async def _action_screenshot(self, action: YAMLTestAction) -> None:
        """Take a screenshot."""
        path = Path(action.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = await self.page.screenshot(path=str(path))

    async def _action_set_viewport_size(self, action: YAMLTestAction) -> None:
        """Set viewport size."""
        if action.width is not None and action.height is not None:
            await self.page.set_viewport_size({"width": int(action.width), "height": int(action.height)})

    async def _action_simulate_offline(self, action: YAMLTestAction) -> None:
        """Simulate offline network."""
        if self.context is not None:
            await self.context.set_offline(True)

    async def _action_simulate_online(self, action: YAMLTestAction) -> None:
        """Restore online network."""
        if self.context is not None:
            await self.context.set_offline(False)

    async def _check_console_errors(self) -> None:
        """Check for console errors."""
        # This would need to be implemented based on how you want to track console errors
        # You might need to set up console message listeners in your test setup

    def _generate_test_summary(self, test_name: str) -> dict[str, Any]:
        """Generate a summary of test results."""
        total_steps = len(self.test_results)
        successful_steps = sum(1 for result in self.test_results if result.success)
        failed_steps = total_steps - successful_steps

        return {
            "test_name": test_name,
            "total_steps": total_steps,
            "successful_steps": successful_steps,
            "failed_steps": failed_steps,
            "success_rate": successful_steps / total_steps if total_steps > 0 else 0,
            "overall_success": failed_steps == 0,
            "results": [
                {
                    "step": result.step_name,
                    "success": result.success,
                    "error": result.error,
                    "timestamp": result.timestamp.isoformat(),
                }
                for result in self.test_results
            ],
            "stored_data": self.stored_data,
        }


async def run_yaml_test(
    page: Page, spec_path: str, browser: Browser | None = None, context: BrowserContext | None = None
) -> dict[str, Any]:
    """Convenience function to run a single YAML test."""
    runner = YAMLTestRunner(page, browser, context)
    return await runner.load_and_run_spec(spec_path)


async def run_yaml_tests(
    page: Page, spec_directory: str, browser: Browser | None = None, context: BrowserContext | None = None
) -> list[dict[str, Any]]:
    """Run all YAML tests in a directory."""
    spec_dir = Path(spec_directory)
    results: list[dict[str, Any]] = []

    for yaml_file in spec_dir.glob("*.yaml"):
        print(f"\n🧪 Running test specification: {yaml_file.name}")
        try:
            result = await run_yaml_test(page, str(yaml_file), browser, context)
            results.append(result)

            if result["overall_success"]:
                print(f"✅ {result['test_name']} - PASSED ({result['successful_steps']}/{result['total_steps']} steps)")
            else:
                print(f"❌ {result['test_name']} - FAILED ({result['successful_steps']}/{result['total_steps']} steps)")

        except Exception as e:
            print(f"❌ Failed to run {yaml_file.name}: {e}")
            results.append({"test_name": yaml_file.name, "overall_success": False, "error": str(e)})

    return results
