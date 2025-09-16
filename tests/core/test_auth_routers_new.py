"""Unit tests for new authentication router endpoints."""

from datetime import datetime
from typing import cast
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, Request, status
from fastapi.testclient import TestClient
import pytest

from faster.core.auth.middlewares import get_current_user
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

    @pytest.mark.asyncio
    async def test_change_password_success(self, client: TestClient) -> None:
        """Test change password endpoint with valid credentials."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(
            AuthService.get_instance(), "change_password", new_callable=AsyncMock
        ) as mock_change_password:
            mock_change_password.return_value = True

            response = client.post(
                "/auth/password/change", json={"current_password": "old_password", "new_password": "new_password"}
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "Password changed successfully" in data["message"]
            assert data["data"]["user_id"] == "user-123"

    @pytest.mark.asyncio
    async def test_change_password_failure(self, client: TestClient) -> None:
        """Test change password endpoint with invalid credentials."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(
            AuthService.get_instance(), "change_password", new_callable=AsyncMock
        ) as mock_change_password:
            mock_change_password.return_value = False

            response = client.post(
                "/auth/password/change", json={"current_password": "wrong_password", "new_password": "new_password"}
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "failed"
            assert "Failed to change password" in data["message"]

    @pytest.mark.asyncio
    async def test_change_password_missing_data(self, client: TestClient) -> None:
        """Test change password endpoint with missing data."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        response = client.post(
            "/auth/password/change",
            json={"current_password": "old_password"},  # Missing new_password
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "failed"
        assert "required" in data["message"]

    @pytest.mark.asyncio
    async def test_change_password_unauthenticated(self, client: TestClient) -> None:
        """Test change password endpoint without authentication."""

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return None

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        response = client.post(
            "/auth/password/change", json={"current_password": "old_password", "new_password": "new_password"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "failed"
        assert "Authentication required" in data["message"]

    @pytest.mark.asyncio
    async def test_initiate_password_reset_success(self, client: TestClient) -> None:
        """Test initiate password reset endpoint."""
        with patch.object(AuthService.get_instance(), "initiate_password_reset", new_callable=AsyncMock) as mock_reset:
            mock_reset.return_value = True

            response = client.post("/auth/password/reset/initiate", json={"email": "test@example.com"})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "Password reset email sent" in data["message"]

    @pytest.mark.asyncio
    async def test_initiate_password_reset_missing_email(self, client: TestClient) -> None:
        """Test initiate password reset endpoint without email."""
        response = client.post("/auth/password/reset/initiate", json={})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "failed"
        assert "Email address is required" in data["message"]

    @pytest.mark.asyncio
    async def test_confirm_password_reset_success(self, client: TestClient) -> None:
        """Test confirm password reset endpoint."""
        with patch.object(AuthService.get_instance(), "confirm_password_reset", new_callable=AsyncMock) as mock_confirm:
            mock_confirm.return_value = True

            response = client.post(
                "/auth/password/reset/confirm", json={"token": "reset_token", "new_password": "new_password"}
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "Password reset completed successfully" in data["message"]

    @pytest.mark.asyncio
    async def test_confirm_password_reset_invalid_token(self, client: TestClient) -> None:
        """Test confirm password reset endpoint with invalid token."""
        with patch.object(AuthService.get_instance(), "confirm_password_reset", new_callable=AsyncMock) as mock_confirm:
            mock_confirm.return_value = False

            response = client.post(
                "/auth/password/reset/confirm", json={"token": "invalid_token", "new_password": "new_password"}
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "failed"
            assert "Invalid or expired reset token" in data["message"]

    # =============================================================================
    # Account Management Tests
    # =============================================================================

    @pytest.mark.asyncio
    async def test_deactivate_account_success(self, client: TestClient) -> None:
        """Test deactivate account endpoint."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "deactivate_account", new_callable=AsyncMock) as mock_deactivate:
            mock_deactivate.return_value = True

            response = client.post("/auth/account/deactivate", json={"password": "correct_password"})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "Account deactivated successfully" in data["message"]

    @pytest.mark.asyncio
    async def test_deactivate_account_wrong_password(self, client: TestClient) -> None:
        """Test deactivate account endpoint with wrong password."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "deactivate_account", new_callable=AsyncMock) as mock_deactivate:
            mock_deactivate.return_value = False

            response = client.post("/auth/account/deactivate", json={"password": "wrong_password"})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "failed"
            assert "Failed to deactivate account" in data["message"]

    @pytest.mark.asyncio
    async def test_delete_account_success(self, client: TestClient) -> None:
        """Test delete account endpoint."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "delete_account", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = True

            response = client.post(
                "/auth/account/delete", json={"password": "correct_password", "confirmation": "DELETE"}
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "Account deleted successfully" in data["message"]

    @pytest.mark.asyncio
    async def test_delete_account_wrong_confirmation(self, client: TestClient) -> None:
        """Test delete account endpoint with wrong confirmation."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        response = client.post("/auth/account/delete", json={"password": "correct_password", "confirmation": "WRONG"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "failed"
        assert "Password and confirmation ('DELETE') are required" in data["message"]

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

            response = client.post("/auth/admin/users/target-user-123/ban", json={"reason": "Violation of terms"})

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

            response = client.post("/auth/admin/users/target-user-123/ban", json={"reason": "Violation of terms"})

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

            response = client.post("/auth/admin/users/target-user-123/unban")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "User unbanned successfully" in data["message"]

    # =============================================================================
    # Role Management Tests (Admin Only)
    # =============================================================================

    @pytest.mark.asyncio
    async def test_grant_roles_success(self, client: TestClient) -> None:
        """Test grant roles endpoint (admin only)."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "grant_roles", new_callable=AsyncMock) as mock_grant:
            mock_grant.return_value = True

            response = client.post(
                "/auth/admin/users/target-user-123/roles/grant", json={"roles": ["moderator", "editor"]}
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "Roles granted successfully" in data["message"]
            assert data["data"]["granted_roles"] == ["moderator", "editor"]

    @pytest.mark.asyncio
    async def test_grant_roles_invalid_data(self, client: TestClient) -> None:
        """Test grant roles endpoint with invalid data."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        response = client.post(
            "/auth/admin/users/target-user-123/roles/grant",
            json={"roles": "not_a_list"},  # Should be a list
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "failed"
        assert "Roles list is required" in data["message"]

    @pytest.mark.asyncio
    async def test_revoke_roles_success(self, client: TestClient) -> None:
        """Test revoke roles endpoint (admin only)."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "revoke_roles", new_callable=AsyncMock) as mock_revoke:
            mock_revoke.return_value = True

            response = client.post("/auth/admin/users/target-user-123/roles/revoke", json={"roles": ["moderator"]})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "Roles revoked successfully" in data["message"]
            assert data["data"]["revoked_roles"] == ["moderator"]

    @pytest.mark.asyncio
    async def test_get_user_roles_success(self, client: TestClient) -> None:
        """Test get user roles endpoint (admin only)."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "get_user_roles_by_id", new_callable=AsyncMock) as mock_get_roles:
            mock_get_roles.return_value = ["admin", "user"]

            response = client.get("/auth/admin/users/target-user-123/roles")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "success"
            assert "User roles retrieved successfully" in data["message"]
            assert data["data"]["roles"] == ["admin", "user"]

    @pytest.mark.asyncio
    async def test_get_user_roles_permission_denied(self, client: TestClient) -> None:
        """Test get user roles endpoint with permission denied."""
        mock_user = self.create_mock_user()

        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch.object(AuthService.get_instance(), "get_user_roles_by_id", new_callable=AsyncMock) as mock_get_roles:
            mock_get_roles.return_value = None  # Permission denied

            response = client.get("/auth/admin/users/target-user-123/roles")

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
            AuthService.get_instance(), "change_password", new_callable=AsyncMock
        ) as mock_change_password:
            mock_change_password.side_effect = Exception("Database connection failed")

            response = client.post(
                "/auth/password/change", json={"current_password": "old_password", "new_password": "new_password"}
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "failed"
            assert "An error occurred" in data["message"]
