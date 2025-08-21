"""Handles the Supabase client initialization and session management."""

from functools import lru_cache

from supabase import Client, create_client
from supabase.client import ClientOptions

from faster.core.config import default_settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Creates and returns a Supabase client instance.

    Utilizes LRU cache to ensure a single instance is created and reused.

    Returns:
        A Supabase client instance.

    Raises:
        ValueError: If Supabase URL or anonymous key is not configured.
    """
    if not default_settings.supabase_url or not default_settings.supabase_anon_key:
        raise ValueError("Supabase URL and anonymous key must be configured.")

    return create_client(
        default_settings.supabase_url,
        default_settings.supabase_anon_key,
        options=ClientOptions(
            persist_session=False,  # Disable session persistence for server-side usage
            auto_refresh_token=True,
        ),
    )


def get_auth() -> Client:
    """
    Utility function to retrieve the Supabase Auth client.

    This function is a convenience wrapper around get_supabase_client()
    to provide direct access to the authentication functionalities.

    Returns:
        The Supabase Auth client instance.
    """
    return get_supabase_client()
