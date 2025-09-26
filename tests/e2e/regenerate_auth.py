#!/usr/bin/env python3
"""
Simple script to regenerate E2E authentication credentials.
This script removes expired credentials and triggers new authentication setup.
"""

import asyncio
from pathlib import Path
import sys

from tests.e2e.auth_handler import SupabaseAuthHandler
from tests.e2e.setup_teardown import E2ETestSetup

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


async def regenerate_authentication() -> bool:
    """Regenerate authentication credentials for E2E tests."""
    print("🔄 Regenerating E2E authentication credentials...")

    # Clean up existing credentials
    auth_handler = SupabaseAuthHandler()

    if auth_handler.auth_file_path.exists():
        print("🗑️  Removing expired authentication file...")
        auth_handler.auth_file_path.unlink()

    # Clear any cached session data
    print("🧹 Clearing cached session data...")

    # Run the setup process
    print("🚀 Starting authentication setup...")
    setup = E2ETestSetup()
    success = await setup.global_setup()

    if success:
        print("✅ Authentication regeneration completed successfully!")
        print("🧪 You can now run E2E tests with: make test-e2e")
        return True
    print("❌ Authentication regeneration failed!")
    print("💡 Please check your network connection and try again.")
    print("🔧 Make sure the development server is running: make dev")
    return False


async def check_authentication_status() -> None:
    """Check the current authentication status."""
    print("🔍 Checking authentication status...")

    auth_handler = SupabaseAuthHandler()
    session_data = await auth_handler.load_cached_session()

    if session_data:
        print("✅ Valid authentication session found!")
        print(f"📧 User: {session_data.get('user', {}).get('email', 'Unknown')}")
        print(f"⏰ Expires: {session_data.get('expires_at', 'Unknown')}")
    else:
        print("❌ No valid authentication session found.")
        print("🔧 Run this script to generate new credentials.")


async def main() -> None:
    """Main function."""
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        await check_authentication_status()
        return

    print("🚀 E2E Authentication Regeneration Tool")
    print("=" * 50)

    # Check current status first
    await check_authentication_status()
    print()

    # Ask user if they want to regenerate
    response = input("Do you want to regenerate authentication credentials? (y/N): ")
    if response.lower() not in ["y", "yes"]:
        print("👋 Cancelled by user.")
        return

    # Regenerate authentication
    success = await regenerate_authentication()

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
