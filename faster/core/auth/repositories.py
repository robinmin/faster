from supabase import create_client

from ..config import default_settings


class AuthRepository:
    """Repository for authentication-related database operations."""

    def __init__(self) -> None:
        """Initialize the repository with a Supabase client using service key for admin access."""
        self._supabase = create_client(default_settings.supabase_url or "", default_settings.supabase_service_key or "")

    async def check_user_profile_exists(self, user_id: str) -> bool:
        """
        Check if a user profile exists in the profiles table.
        This is used to determine if a user has completed onboarding.
        """
        try:
            # Try to fetch the user's profile
            response = self._supabase.table("profiles").select("*").eq("id", user_id).execute()
            return len(response.data) > 0
        except Exception:
            # If there's any error, assume the profile doesn't exist
            return False
