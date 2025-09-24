"""Unit tests for new authentication router endpoints."""

from datetime import datetime
from typing import cast
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, Request, status
from fastapi.testclient import TestClient
import pytest

from faster.core.auth.middlewares import AuthMiddleware, get_current_user
from faster.core.auth.models import UserProfileData
from faster.core.auth.routers import router
from faster.core.auth.services import AuthService


class TestNewAuthEndpoints:
    """Test new authentication endpoints added for enterprise features."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create a FastAPI app with auth router."""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create a test client."""
        client = TestClient(app, follow_redirects=False)
        assert isinstance(client.app, FastAPI)
        return client

    def create_mock_user(self) -> UserProfileData:
        """Create a mock user profile."""
        return UserProfileData(
            id="user-123",
            email="test@example.com",
            email_confirmed_at=None,
            phone=None,
            created_at=datetime(2023, 1, 1),
            updated_at=datetime(2023, 1, 1),
            last_sign_in_at=None,
            app_metadata={},
            user_metadata={},
            aud="test",
            role="authenticated",
        )

    # =============================================================================
    # Password Management Tests
    # =============================================================================
    #
    # NOTE: Password management tests have been removed as password operations
    # are now handled directly by Supabase Auth via the frontend AuthService.
    # This follows Supabase best practices for client-side auth operations.
    #
    # Removed test methods:
    # - test_change_password_success
    # - test_change_password_failure
    # - test_change_password_missing_data
    # - test_change_password_unauthenticated
    # - test_initiate_password_reset_success
    # - test_initiate_password_reset_missing_email
    # - test_confirm_password_reset_success
    # - test_confirm_password_reset_invalid_token

    # =============================================================================
    # Account Management Tests
    # =============================================================================

    @pytest.mark.asyncio
    async def test_deactivate_success(self, client: TestClient) -> None:
        """Test comprehensive deactivate account endpoint."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "deactivate", new_callable=AsyncMock) as mock_deactivate:
            mock_deactivate.return_value = True

            response = client.post("/auth/deactivate", json={"password": "correct_password"})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "Account deactivated successfully" in data["message"]

    @pytest.mark.asyncio
    async def test_deactivate_wrong_password(self, client: TestClient) -> None:
        """Test deactivate account endpoint with wrong password."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "deactivate", new_callable=AsyncMock) as mock_deactivate:
            mock_deactivate.return_value = False

            response = client.post("/auth/deactivate", json={"password": "wrong_password"})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "failed"
            assert "Failed to deactivate account" in data["message"]

    # =============================================================================
    # User Administration Tests (Admin Only)
    # =============================================================================

    @pytest.mark.asyncio
    async def test_ban_user_success(self, client: TestClient) -> None:
        """Test ban user endpoint (admin only)."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "ban_user", new_callable=AsyncMock) as mock_ban:
            mock_ban.return_value = True

            response = client.post("/auth/users/target-user-123/ban", json={"reason": "Violation of terms"})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "User banned successfully" in data["message"]
            assert data["data"]["target_user_id"] == "target-user-123"

    @pytest.mark.asyncio
    async def test_ban_user_insufficient_permissions(self, client: TestClient) -> None:
        """Test ban user endpoint with insufficient permissions."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "ban_user", new_callable=AsyncMock) as mock_ban:
            mock_ban.return_value = False

            response = client.post("/auth/users/target-user-123/ban", json={"reason": "Violation of terms"})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "failed"
            assert "Insufficient permissions" in data["message"]

    @pytest.mark.asyncio
    async def test_unban_user_success(self, client: TestClient) -> None:
        """Test unban user endpoint (admin only)."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "unban_user", new_callable=AsyncMock) as mock_unban:
            mock_unban.return_value = True

            response = client.post("/auth/users/target-user-123/unban")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "User unbanned successfully" in data["message"]

    @pytest.mark.asyncio
    async def test_ban_user_by_email_success(self, client: TestClient) -> None:
        """Test ban user endpoint with email identifier (admin only)."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "ban_user", new_callable=AsyncMock) as mock_ban:
            mock_ban.return_value = True

            response = client.post("/auth/users/user@example.com/ban", json={"reason": "Violation of terms"})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "User banned successfully" in data["message"]
            assert data["data"]["target_user_id"] == "user@example.com"

            # Verify the service was called with the email
            mock_ban.assert_called_once_with("user-123", "user@example.com", "Violation of terms")

    @pytest.mark.asyncio
    async def test_ban_user_by_email_user_not_found(self, client: TestClient) -> None:
        """Test ban user endpoint with non-existent email."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "ban_user", new_callable=AsyncMock) as mock_ban:
            mock_ban.return_value = False  # User not found or no permission

            response = client.post("/auth/users/nonexistent@example.com/ban", json={"reason": "Test"})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "failed"
            assert "Insufficient permissions" in data["message"]

    @pytest.mark.asyncio
    async def test_unban_user_by_email_success(self, client: TestClient) -> None:
        """Test unban user endpoint with email identifier (admin only)."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "unban_user", new_callable=AsyncMock) as mock_unban:
            mock_unban.return_value = True

            response = client.post("/auth/users/user@example.com/unban")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "User unbanned successfully" in data["message"]

            # Verify the service was called with the email
            mock_unban.assert_called_once_with("user-123", "user@example.com")

    @pytest.mark.asyncio
    async def test_unban_user_by_email_user_not_found(self, client: TestClient) -> None:
        """Test unban user endpoint with non-existent email."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "unban_user", new_callable=AsyncMock) as mock_unban:
            mock_unban.return_value = False  # User not found or no permission

            response = client.post("/auth/users/nonexistent@example.com/unban")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "failed"
            assert "Failed to unban user" in data["message"]

    # =============================================================================
    # Role Management Tests (Admin Only)
    # =============================================================================

    @pytest.mark.asyncio
    async def test_adjust_roles_success(self, client: TestClient) -> None:
        """Test adjust roles endpoint (admin only)."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "adjust_roles", new_callable=AsyncMock) as mock_adjust:
            mock_adjust.return_value = True

            response = client.post("/auth/users/target-user-123/roles/adjust", json={"roles": ["moderator", "editor"]})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "User roles adjusted successfully" in data["message"]
            assert data["data"]["new_roles"] == ["moderator", "editor"]

    @pytest.mark.asyncio
    async def test_adjust_roles_invalid_data(self, client: TestClient) -> None:
        """Test adjust roles endpoint with invalid data."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        response = client.post(
            "/auth/users/target-user-123/roles/adjust",
            json={"roles": []},  # Empty list should fail
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "failed"
        assert "At least one role is required" in data["message"]

    @pytest.mark.asyncio
    async def test_adjust_roles_by_email_success(self, client: TestClient) -> None:
        """Test adjust roles endpoint with email identifier (admin only)."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "adjust_roles", new_callable=AsyncMock) as mock_adjust:
            mock_adjust.return_value = True

            response = client.post(
                "/auth/users/user@example.com/roles/adjust", json={"roles": ["default", "developer"]}
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "User roles adjusted successfully" in data["message"]
            assert data["data"]["new_roles"] == ["default", "developer"]

            # Verify the service was called with the email
            mock_adjust.assert_called_once_with("user-123", "user@example.com", ["default", "developer"])

    @pytest.mark.asyncio
    async def test_adjust_roles_by_email_user_not_found(self, client: TestClient) -> None:
        """Test adjust roles endpoint with non-existent email."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "adjust_roles", new_callable=AsyncMock) as mock_adjust:
            mock_adjust.return_value = False  # User not found or no permission

            response = client.post("/auth/users/nonexistent@example.com/roles/adjust", json={"roles": ["default"]})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "failed"
            assert "Failed to adjust roles" in data["message"]

    @pytest.mark.asyncio
    async def test_get_user_basic_info_success(self, client: TestClient) -> None:
        """Test get user basic info endpoint (admin only)."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(
            AuthService.get_instance(), "get_user_basic_info_by_id", new_callable=AsyncMock
        ) as mock_get_basic_info:
            mock_get_basic_info.return_value = {
                "id": "target-user-123",
                "email": "test@example.com",
                "status": "active",
                "roles": ["admin", "user"],
            }

            response = client.get("/auth/users/target-user-123/basic")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "User basic information retrieved successfully" in data["message"]
            assert data["data"]["email"] == "test@example.com"
            assert data["data"]["status"] == "active"
            assert data["data"]["roles"] == ["admin", "user"]

    @pytest.mark.asyncio
    async def test_get_user_basic_info_permission_denied(self, client: TestClient) -> None:
        """Test get user basic info endpoint with permission denied."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(
            AuthService.get_instance(), "get_user_basic_info_by_id", new_callable=AsyncMock
        ) as mock_get_basic_info:
            mock_get_basic_info.return_value = None  # Permission denied

            response = client.get("/auth/users/target-user-123/basic")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "failed"
            assert "Insufficient permissions" in data["message"]

    @pytest.mark.asyncio
    async def test_get_user_basic_info_by_email_success(self, client: TestClient) -> None:
        """Test get user basic info endpoint with email identifier."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(
            AuthService.get_instance(), "get_user_basic_info_by_id", new_callable=AsyncMock
        ) as mock_get_basic_info:
            mock_get_basic_info.return_value = {
                "id": "user-456",
                "email": "user@example.com",
                "status": "active",
                "roles": ["default", "developer"],
            }

            response = client.get("/auth/users/user@example.com/basic")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "User basic information retrieved successfully" in data["message"]
            assert data["data"]["email"] == "user@example.com"
            assert data["data"]["id"] == "user-456"
            assert data["data"]["status"] == "active"
            assert data["data"]["roles"] == ["default", "developer"]

            # Verify the service was called with the email
            mock_get_basic_info.assert_called_once_with("user-123", "user@example.com")

    @pytest.mark.asyncio
    async def test_get_user_basic_info_by_email_not_found(self, client: TestClient) -> None:
        """Test get user basic info endpoint with non-existent email."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(
            AuthService.get_instance(), "get_user_basic_info_by_id", new_callable=AsyncMock
        ) as mock_get_basic_info:
            mock_get_basic_info.return_value = None  # User not found

            response = client.get("/auth/users/nonexistent@example.com/basic")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "failed"
            assert "Insufficient permissions" in data["message"]

    # =============================================================================
    # Error Handling Tests
    # =============================================================================

    @pytest.mark.asyncio
    async def test_endpoint_exception_handling(self, client: TestClient) -> None:
        """Test that endpoints handle exceptions gracefully."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(
            AuthService.get_instance(), "deactivate", new_callable=AsyncMock
        ) as mock_deactivate:
            mock_deactivate.side_effect = Exception("Database connection failed")

            response = client.post(
                "/auth/deactivate", json={"password": "test_password"}
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "failed"
            assert "An error occurred" in data["message"]

    # =============================================================================
    # Authentication Middleware Ban/Unban Security Tests
    # =============================================================================

    @pytest.mark.asyncio
    async def test_banned_user_blocked_by_middleware(self, client: TestClient) -> None:
        """Test that banned users are blocked by authentication middleware."""

        # Mock get_user_by_id to return None (simulating soft delete behavior)
        with patch.object(AuthService.get_instance(), "get_user_by_id", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None  # Banned users return None due to soft delete

            # Create middleware instance
            middleware = AuthMiddleware(client.app, require_auth=True)

            # Test the _get_authenticated_user_profile method directly
            result = await middleware._get_authenticated_user_profile("banned-user-123")  # pyright: ignore [reportPrivateUsage]

            # Should return None for banned user (due to soft delete)
            assert result is None
            mock_get_user.assert_called_once_with("banned-user-123", from_cache=True)

    @pytest.mark.asyncio
    async def test_active_user_allowed_by_middleware(self, client: TestClient) -> None:
        """Test that active users are allowed by authentication middleware."""

        # Mock get_user_by_id to return user profile (active users are returned normally)
        with patch.object(AuthService.get_instance(), "get_user_by_id", new_callable=AsyncMock) as mock_get_user:
            mock_user = self.create_mock_user()
            mock_get_user.return_value = mock_user

            # Create middleware instance
            middleware = AuthMiddleware(client.app, require_auth=True)

            # Test the _get_authenticated_user_profile method directly
            result = await middleware._get_authenticated_user_profile("active-user-123")  # pyright: ignore [reportPrivateUsage]

            # Should return user profile for active user
            assert result is not None
            assert result.id == "user-123"
            mock_get_user.assert_called_once_with("active-user-123", from_cache=True)

    @pytest.mark.asyncio
    async def test_deactivated_user_blocked_by_middleware(self, client: TestClient) -> None:
        """Test that deactivated users are blocked by authentication middleware."""
        # Mock get_user_by_id to return None (simulating soft delete behavior)
        with patch.object(AuthService.get_instance(), "get_user_by_id", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None  # Deactivated users return None due to soft delete

            # Create middleware instance
            middleware = AuthMiddleware(client.app, require_auth=True)

            # Test the _get_authenticated_user_profile method directly
            result = await middleware._get_authenticated_user_profile("deactivated-user-123")  # pyright: ignore [reportPrivateUsage]

            # Should return None for deactivated user (due to soft delete)
            assert result is None
            mock_get_user.assert_called_once_with("deactivated-user-123", from_cache=True)

    @pytest.mark.asyncio
    async def test_ban_unban_functionality_with_soft_delete(self, client: TestClient) -> None:
        """Test that ban/unban properly uses soft delete for security."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        # Test ban functionality
        with patch.object(AuthService.get_instance(), "ban_user", new_callable=AsyncMock) as mock_ban:
            mock_ban.return_value = True

            response = client.post("/auth/users/target-user-123/ban", json={"reason": "Test ban"})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            mock_ban.assert_called_once_with("user-123", "target-user-123", "Test ban")

        # Test unban functionality
        with patch.object(AuthService.get_instance(), "unban_user", new_callable=AsyncMock) as mock_unban:
            mock_unban.return_value = True

            response = client.post("/auth/users/target-user-123/unban")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            mock_unban.assert_called_once_with("user-123", "target-user-123")
