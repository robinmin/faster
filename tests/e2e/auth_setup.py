"""
Authentication setup for Playwright tests.
Handles Google OAuth login and session caching.
"""

import asyncio
from pathlib import Path
import sys

from tests.e2e.setup_teardown import E2ETestSetup

# Add the project root to the Python path to fix imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


async def setup_authentication() -> None:
    """Setup authentication for all tests using the unified setup system."""
    print("🚀 Setting up authentication for E2E tests...")

    setup = E2ETestSetup()
    success = await setup.global_setup()

    if success:
        print("✅ Authentication setup completed successfully!")
    else:
        print("❌ Authentication setup failed!")
        raise Exception("Authentication setup failed")


if __name__ == "__main__":
    asyncio.run(setup_authentication())
