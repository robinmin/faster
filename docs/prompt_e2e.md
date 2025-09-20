### Project Background:
- Backend: FastAPI + Supabase Auth (Google OAuth) : backend entry file: `main.py`
- Frontend: Vanilla JS + Supabase JS: Frontend source code file: `@faster/resources/dev-admin.html`
- Tests: I want a **complete, production-ready end-to-end (E2E) test solution** using pytest, pytest-asyncio, pytest-playwright, playwright, and httpx at folder `@tests/e2e`.

### ✅ Requirements

1. **Authentication Handling**
   - Implement login via Google OAuth once, then cache the Supabase session (with refresh token) into `@tests/e2e/playwright-auth.json`.
   - Reuse cached session in later runs.
   - If session is expired, re-run login and update `@tests/e2e/playwright-auth.json`.
   - Provide an alternative approach using Playwright’s `storageState`.

2. **Playwright Config**
   - Use Chromium and Chrome (`channel: 'chrome'`).
   - Add the following option to avoid Google “This browser may not be secure” error:
```
      "--disable-blink-features=AutomationControlled",  # Key flag for Gmail
      "--disable-web-security",
      "--disable-features=VizDisplayCompositor",
      "--disable-dev-shm-usage",
      "--no-sandbox",
      "--disable-extensions"
```
      - Support multiple browser projects (chromium, firefox, webkit).
   - Support running with cached storage state.

3. **Pytest Config**
   - Provide `conftest.py` that:
     - Loads cached session JSON into `localStorage` before tests.
     - Falls back to full login if session expired.
     - Provides fixtures like `page`, `auth_page` (already logged in).
     - Includes helper to refresh Supabase session automatically.

4. **YAML-Driven Test Specs**
   - All page flows should be defined in YAML files under `@tests/e2e/specs/*.yaml`.
   - YAML schema must support:
     - `url`: starting page
     - `steps`: list of actions (`fill`, `click`, `wait_for`, `assert_text`, `assert_visible`, `assert_url`)
   - Example YAML file for login page and dashboard page.
   - Provide a Python runner that:
     - Reads YAML
     - Maps actions to Playwright commands
     - Executes steps sequentially
     - Asserts expected results

5. **Sample Tests**
   - E2E test for login flow (using cached session).
   - E2E test for visiting dashboard, performing CRUD action, verifying updated data.
   - E2E test for expired session (should trigger re-login).
   - E2E test for network error simulation and error UI check.
   - E2E test for multiple browsers.

6. **CI/CD Setup**
   - Add two make tasks:
     - `make test-e2e`: Run all E2E tests automatically
     - `make test-e2e-manual`: Run all E2E tests with manual intervention for login with Google OAuth, so that we can cache the credential JSON file into `@tests/e2e/playwright-auth.json`

7. **Edge Cases**
   - Token expiration and refresh
   - Browser compatibility (chromium, firefox, webkit)
   - CI/CD non-interactive Google login flows
   - Handling flaky selectors or timeouts

### 🎯 Deliverables
- All generated files should be placed in the `@tests/e2e` directory except the Makefile itself.
- `playwright_config.py`
- `conftest.py`
- Example E2E tests (`test_login.py`, `test_dashboard.py`, `test_flows.py`)
- Example YAML specs (`login.yaml`, `dashboard.yaml`)
- YAML runner implementation
- README instructions for running E2E tests

Make the solution **secure, modular, YAML-driven, production-ready, and easy to maintain**.
