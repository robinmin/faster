from unittest.mock import MagicMock, patch

import pytest

from faster.core.auth.repositories import AuthRepository


class TestAuthRepository:
    """Test AuthRepository class."""

    @pytest.fixture
    def auth_repository(self) -> AuthRepository:
        """Create AuthRepository instance with mocked settings."""
        with (
            patch("faster.core.auth.repositories.default_settings") as mock_settings,
            patch("faster.core.auth.repositories.create_client") as mock_create_client,
        ):
            mock_settings.supabase_url = "https://test.supabase.co"
            mock_settings.supabase_service_key = "test-service-key"
            mock_supabase = MagicMock()
            mock_create_client.return_value = mock_supabase
            repo = AuthRepository()
            repo._supabase = mock_supabase  # Ensure we use our mock
            return repo

    def test_auth_repository_initialization(self, auth_repository: AuthRepository) -> None:
        """Test AuthRepository initialization."""
        assert auth_repository is not None
        assert hasattr(auth_repository, "_supabase")

    @pytest.mark.asyncio
    async def test_check_user_profile_exists_true(self, auth_repository: AuthRepository) -> None:
        """Test check_user_profile_exists returns True when profile exists."""
        # Mock the Supabase client and response
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_execute = MagicMock()

        # Set up the mock chain
        auth_repository._supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = mock_execute
        mock_execute.data = [{"id": "user-123", "name": "Test User"}]  # Profile exists

        result = await auth_repository.check_user_profile_exists("user-123")

        assert result is True
        auth_repository._supabase.table.assert_called_once_with("profiles")
        mock_table.select.assert_called_once()
        mock_select.eq.assert_called_once_with("id", "user-123")
        mock_eq.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_user_profile_exists_false(self, auth_repository: AuthRepository) -> None:
        """Test check_user_profile_exists returns False when profile doesn't exist."""
        # Mock the Supabase client and response
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_execute = MagicMock()

        # Set up the mock chain
        auth_repository._supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = mock_execute
        mock_execute.data = []  # No profile exists

        result = await auth_repository.check_user_profile_exists("user-123")

        assert result is False
        auth_repository._supabase.table.assert_called_once_with("profiles")
        mock_table.select.assert_called_once()
        mock_select.eq.assert_called_once_with("id", "user-123")
        mock_eq.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_user_profile_exists_exception(self, auth_repository: AuthRepository) -> None:
        """Test check_user_profile_exists returns False when an exception occurs."""
        # Mock the Supabase client to raise an exception
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()

        # Set up the mock chain
        auth_repository._supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.side_effect = Exception("Database error")

        result = await auth_repository.check_user_profile_exists("user-123")

        assert result is False
        auth_repository._supabase.table.assert_called_once_with("profiles")
        mock_table.select.assert_called_once()
        mock_select.eq.assert_called_once_with("id", "user-123")
        mock_eq.execute.assert_called_once()
