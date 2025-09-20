#!/usr/bin/env python3
"""
Wait for server to be ready before running E2E tests.
"""

from pathlib import Path
import sys
import time

import httpx


def wait_for_server(url: str = "http://127.0.0.1:8000/dev/admin", timeout: int = 30) -> bool:
    """Wait for server to be responsive."""
    print(f"🔍 Checking if server is ready at {url}...")

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = httpx.get(url, timeout=5.0)
            if response.status_code == 200:
                print(f"✅ Server is ready at {url}")
                return True
        except (httpx.RequestError, httpx.TimeoutException):
            pass

        print("⏳ Server not ready yet, waiting...")
        time.sleep(2)

    print(f"❌ Server did not become ready within {timeout} seconds")
    return False


if __name__ == "__main__":
    # Add project root to Python path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    if not wait_for_server():
        sys.exit(1)
