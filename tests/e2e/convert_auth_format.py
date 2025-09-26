#!/usr/bin/env python3
"""
Convert existing auth file from custom format to Playwright storage_state format.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.e2e.auth_handler import SupabaseAuthHandler


async def convert_auth_format():
    """Convert existing auth file to Playwright format."""
    print("🔄 Converting authentication file to Playwright format...")
    
    auth_handler = SupabaseAuthHandler()
    
    if not auth_handler.auth_file_path.exists():
        print("❌ No authentication file found to convert")
        return False
    
    try:
        # Load the existing session (this will handle format conversion)
        session_data = await auth_handler.load_cached_session()
        
        if not session_data:
            print("❌ No valid session data found or session expired")
            return False
        
        # Save it back (this will save in Playwright format)
        await auth_handler.save_session(session_data)
        
        print("✅ Authentication file converted to Playwright format successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to convert authentication file: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(convert_auth_format())
    if not success:
        sys.exit(1)
