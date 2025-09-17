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


class TestAuthRouters:
    """Test auth router endpoints."""

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
        # Ensure mypy knows client.app is the FastAPI app
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

    @pytest.mark.asyncio
    async def test_onboarding_endpoint_authenticated_user_with_profile(self, client: TestClient) -> None:
        """Test onboarding endpoint for authenticated user with completed profile."""
        # Mock the get_current_user dependency to return a user
        mock_user = self.create_mock_user()

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            # Mock the auth service singleton instance method
            with patch.object(AuthService.get_instance(), "check_user_onboarding_complete", new_callable=AsyncMock) as mock_check_onboarding:
                mock_check_onboarding.return_value = True

                # Make a request to the endpoint
                response = client.get("/auth/onboarding")

                # Check that it's a JSON response
                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "application/json"

                # Parse the JSON response
                data = response.json()

                # Check the response structure
                assert "status" in data
                assert data["status"] == "redirect"
                assert "message" in data
                assert "Welcome back, my friend!" in data["message"]
                assert "data" in data
                assert isinstance(data["data"], dict)
                assert data["data"]["user_id"] == "user-123"

    @pytest.mark.asyncio
    async def test_onboarding_endpoint_authenticated_user_without_profile(self, client: TestClient) -> None:
        """Test onboarding endpoint for authenticated user without completed profile."""
        # Mock the get_current_user dependency to return a user
        mock_user = self.create_mock_user()

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            # Mock the auth service singleton instance method
            with patch.object(AuthService.get_instance(), "check_user_onboarding_complete", new_callable=AsyncMock) as mock_check_onboarding:
                mock_check_onboarding.return_value = False

                # Make a request to the endpoint
                response = client.get("/auth/onboarding")

                # Check that it's a JSON response
                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "application/json"

                # Parse the JSON response
                data = response.json()

                # Check the response structure
                assert "status" in data
                assert data["status"] == "success"
                assert "message" in data
                assert "data" in data
                assert isinstance(data["data"], dict)
                assert data["data"]["user_id"] == "user-123"
                assert data["data"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_onboarding_endpoint_non_authenticated_user(self, client: TestClient) -> None:
        """Test onboarding endpoint for non-authenticated user."""

        # Override the app's dependency to return None (no authenticated user)
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return None

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None

            # Make a request to the endpoint
            response = client.get("/auth/onboarding")

            # Check that it's a JSON response
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "application/json"

            # Parse the JSON response
            data = response.json()

            # Check the response structure
            assert "status" in data
            assert data["status"] == "failed"
            assert "message" in data
            assert "Authentication required. Please login first." in data["message"]
            assert "data" in data
            assert data["data"] == {}

    @pytest.mark.asyncio
    async def test_dashboard_endpoint_authenticated_user_with_profile(self, client: TestClient) -> None:
        """Test dashboard endpoint for authenticated user with completed profile."""
        # Mock the get_current_user dependency to return a user
        mock_user = self.create_mock_user()

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            # Mock the auth service singleton instance method
            with patch.object(AuthService.get_instance(), "check_user_onboarding_complete", new_callable=AsyncMock) as mock_check_onboarding:
                mock_check_onboarding.return_value = True

                # Make a request to the endpoint
                response = client.get("/auth/dashboard")

                # Check that it's a JSON response
                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "application/json"

                # Parse the JSON response
                data = response.json()

                # Check the response structure
                assert "status" in data
                assert data["status"] == "success"
                assert "message" in data
                assert "data" in data
                assert isinstance(data["data"], dict)
                assert data["data"]["user_id"] == "user-123"
                assert data["data"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_dashboard_endpoint_authenticated_user_without_profile(self, client: TestClient) -> None:
        """Test dashboard endpoint for authenticated user without completed profile."""
        # Mock the get_current_user dependency to return a user
        mock_user = self.create_mock_user()

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            # Mock the auth service singleton instance method
            with patch.object(AuthService.get_instance(), "check_user_onboarding_complete", new_callable=AsyncMock) as mock_check_onboarding:
                mock_check_onboarding.return_value = False

                # Make a request to the endpoint
                response = client.get("/auth/dashboard")

                # Check that it's a JSON response
                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "application/json"
                data = response.json()
                assert "status" in data
                assert data["status"] == "failed"
                assert "message" in data
                assert "Onboarding required. Please complete your profile setup." in data["message"]
                assert "data" in data
                assert data["data"]["user_id"] == "user-123"

    @pytest.mark.asyncio
    async def test_dashboard_endpoint_non_authenticated_user(self, client: TestClient) -> None:
        """Test dashboard endpoint for non-authenticated user."""

        # Override the app's dependency to return None (no authenticated user)
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return None

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None

            # Make a request to the endpoint
            response = client.get("/auth/dashboard")

            # Check that it's a JSON response
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "application/json"

            data = response.json()
            assert "status" in data
            assert data["status"] == "failed"
            assert "message" in data
            assert "Authentication required. Please login first." in data["message"]
            assert "data" in data
            assert data["data"] == {}

    @pytest.mark.asyncio
    async def test_profile_endpoint_authenticated_user_with_profile(self, client: TestClient) -> None:
        """Test profile endpoint for authenticated user with completed profile."""
        # Mock the get_current_user dependency to return a user
        mock_user = self.create_mock_user()

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            # Mock the auth service singleton instance method
            with patch.object(AuthService.get_instance(), "check_user_onboarding_complete", new_callable=AsyncMock) as mock_check_onboarding:
                mock_check_onboarding.return_value = True

                # Make a request to the endpoint
                response = client.get("/auth/profile")

                # Check that it's a JSON response
                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "application/json"

                # Parse the JSON response
                data = response.json()

                # Check the response structure
                assert "status" in data
                assert data["status"] == "success"
                assert "message" in data
                assert "data" in data
                assert isinstance(data["data"], dict)

                # Check basic user information
                assert data["data"]["id"] == "user-123"
                assert data["data"]["email"] == "test@example.com"
                assert data["data"]["email_confirmed_at"] is None
                assert "2023-01-01T00:00:00" in str(data["data"]["created_at"])
                assert data["data"]["last_sign_in_at"] is None

                # Check new fields from the updated profile endpoint
                assert "username" in data["data"]
                assert "roles" in data["data"]
                assert "avatar_url" in data["data"]
                assert "confirmed_at" in data["data"]
                assert "updated_at" in data["data"]
                assert "app_metadata" in data["data"]

                # Check metadata fields
                assert data["data"]["user_metadata"] == {}
                assert data["data"]["app_metadata"] == {}

                # Check roles (should be empty list since request.state.roles is not set in test)
                assert data["data"]["roles"] == []

                # Check that username is None (since user_metadata is empty)
                assert data["data"]["username"] is None

                # Check that avatar_url is None (since no avatar in metadata)
                assert data["data"]["avatar_url"] is None

                # Check confirmed_at and updated_at (should match created_at from mock user)
                assert data["data"]["confirmed_at"] is None  # Not set in mock user
                assert "2023-01-01T00:00:00" in str(data["data"]["updated_at"])

    @pytest.mark.asyncio
    async def test_profile_endpoint_authenticated_user_without_profile(self, client: TestClient) -> None:
        """Test profile endpoint for authenticated user without completed profile."""
        # Mock the get_current_user dependency to return a user
        mock_user = self.create_mock_user()

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            # Mock the auth service singleton instance method
            with patch.object(AuthService.get_instance(), "check_user_onboarding_complete", new_callable=AsyncMock) as mock_check_onboarding:
                mock_check_onboarding.return_value = False

                # Make a request to the endpoint
                response = client.get("/auth/profile")

                # Check that it's either a redirect response or a JSON response
                if response.status_code == status.HTTP_303_SEE_OTHER:
                    # Redirect response
                    assert response.headers["location"] == "/auth/onboarding"
                else:
                    # JSON response
                    assert response.status_code == status.HTTP_200_OK
                    assert response.headers["content-type"] == "application/json"
                    data = response.json()
                    assert "status" in data
                    assert "message" in data
                    # Should contain onboarding-related content
                    assert "onboarding" in data["message"].lower() or "profile" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_profile_endpoint_non_authenticated_user(self, client: TestClient) -> None:
        """Test profile endpoint for non-authenticated user."""

        # Override the app's dependency to return None (no authenticated user)
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return None

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None

            # Make a request to the endpoint
            response = client.get("/auth/profile")

            # Should return JSON response with failed status
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "application/json"
            data = response.json()
            assert "status" in data
            assert data["status"] == "failed"
            assert "message" in data
            assert "Authentication required" in data["message"]
            assert "data" in data
            assert data["data"] == {}

    @pytest.mark.asyncio
    async def test_callback_endpoint_signed_in_event(self, client: TestClient) -> None:
        """Test callback endpoint for SIGNED_IN event with authenticated user."""
        # Mock the get_current_user dependency to return a user
        mock_user = self.create_mock_user()

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            with (
                patch("faster.core.auth.routers.extract_bearer_token_from_request", return_value="mock_token"),
                patch("faster.core.auth.routers.blacklist_delete", new_callable=AsyncMock) as mock_blacklist_delete,
                patch(
    "faster.core.auth.services.AuthService.should_update_user_in_db", new_callable=AsyncMock
                ) as mock_should_update,
            ):
                mock_blacklist_delete.return_value = None
                mock_should_update.return_value = False

                # Test SIGNED_IN event
                response = client.post("/auth/callback/SIGNED_IN")

                # Check that it's a JSON response
                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "application/json"

                # Parse the JSON response
                data = response.json()

                # Check the response structure
                assert "status" in data
                assert data["status"] == "success"
                assert "message" in data
                assert "User signed in successfully" in data["message"]
                assert "data" in data
                assert isinstance(data["data"], dict)
                assert data["data"]["event"] == "SIGNED_IN"
                assert data["data"]["user_id"] == "user-123"

    @pytest.mark.asyncio
    async def test_callback_endpoint_signed_in_event_with_developer_role(self, client: TestClient) -> None:
        """Test callback endpoint for SIGNED_IN event with developer user includes available roles."""
        # Mock the get_current_user dependency to return a user
        mock_user = self.create_mock_user()

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            with (
                patch("faster.core.auth.routers.extract_bearer_token_from_request", return_value="mock_token"),
                patch("faster.core.auth.routers.blacklist_delete", new_callable=AsyncMock) as mock_blacklist_delete,
                patch("faster.core.auth.routers.has_role", new_callable=AsyncMock) as mock_has_role,
                patch.object(
                    AuthService, "should_update_user_in_db", new_callable=AsyncMock
                ) as mock_should_update,
                patch("faster.core.auth.services.AppRepository") as mock_app_repository_class,
            ):
                mock_blacklist_delete.return_value = None
                mock_should_update.return_value = False
                mock_has_role.return_value = True  # User has developer role

                # Mock AppRepository instance and its get_sys_dict method
                mock_app_repository = AsyncMock()
                mock_app_repository.get_sys_dict.return_value = {
                    "user_role": {10: "default", 20: "developer", 30: "admin", 40: "moderator"}
                }
                mock_app_repository_class.return_value = mock_app_repository

                # Test SIGNED_IN event
                response = client.post("/auth/callback/SIGNED_IN")

                # Check that it's a JSON response
                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "application/json"

                # Parse the JSON response
                data = response.json()

                # Check the response structure
                assert "status" in data
                assert data["status"] == "success"
                assert "message" in data
                assert "User signed in successfully" in data["message"]
                assert "data" in data
                assert isinstance(data["data"], dict)
                assert data["data"]["event"] == "SIGNED_IN"
                assert data["data"]["user_id"] == "user-123"

                # Check that available_roles is included for developer
                assert "available_roles" in data["data"]
                expected_roles = ["admin", "default", "developer", "moderator"]  # Sorted
                assert data["data"]["available_roles"] == expected_roles

                # Verify that has_role was called with "developer"
                mock_has_role.assert_called_once()
                # Verify that AppRepository.get_sys_dict was called with correct category
                mock_app_repository.get_sys_dict.assert_called_once_with(category="user_role")

    @pytest.mark.asyncio
    async def test_callback_endpoint_signed_in_event_without_developer_role(self, client: TestClient) -> None:
        """Test callback endpoint for SIGNED_IN event with non-developer user excludes available roles."""
        # Mock the get_current_user dependency to return a user
        mock_user = self.create_mock_user()

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            with (
                patch("faster.core.auth.routers.extract_bearer_token_from_request", return_value="mock_token"),
                patch("faster.core.auth.routers.blacklist_delete", new_callable=AsyncMock) as mock_blacklist_delete,
                patch("faster.core.auth.routers.has_role", new_callable=AsyncMock) as mock_has_role,
                patch.object(
                    AuthService, "should_update_user_in_db", new_callable=AsyncMock
                ) as mock_should_update,
                patch("faster.core.auth.services.AppRepository") as mock_app_repository_class,
            ):
                mock_blacklist_delete.return_value = None
                mock_should_update.return_value = False
                mock_has_role.return_value = False  # User does NOT have developer role

                # Mock AppRepository instance (should not be called for non-developer)
                mock_app_repository = AsyncMock()
                mock_app_repository_class.return_value = mock_app_repository

                # Test SIGNED_IN event
                response = client.post("/auth/callback/SIGNED_IN")

                # Check that it's a JSON response
                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "application/json"

                # Parse the JSON response
                data = response.json()

                # Check the response structure
                assert "status" in data
                assert data["status"] == "success"
                assert "message" in data
                assert "User signed in successfully" in data["message"]
                assert "data" in data
                assert isinstance(data["data"], dict)
                assert data["data"]["event"] == "SIGNED_IN"
                assert data["data"]["user_id"] == "user-123"

                # Check that available_roles is NOT included for non-developer
                assert "available_roles" not in data["data"]

                # Verify that has_role was called with "developer"
                mock_has_role.assert_called_once()
                # Verify that AppRepository.get_sys_dict was NOT called for non-developer
                mock_app_repository.get_sys_dict.assert_not_called()

    @pytest.mark.asyncio
    async def test_callback_endpoint_signed_out_event(self, client: TestClient) -> None:
        """Test callback endpoint for SIGNED_OUT event with authenticated user."""
        # Mock the get_current_user dependency to return a user
        mock_user = self.create_mock_user()

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            with (
                patch("faster.core.auth.routers.extract_bearer_token_from_request", return_value="mock_token"),
                patch(
    "faster.core.auth.services.AuthService.background_process_logout", new_callable=AsyncMock
                ) as mock_bg_logout,
            ):
                mock_bg_logout.return_value = None

                # Test SIGNED_OUT event
                response = client.post("/auth/callback/SIGNED_OUT")

                # Check that it's a JSON response
                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "application/json"

                # Parse the JSON response
                data = response.json()

                # Check the response structure
                assert "status" in data
                assert data["status"] == "success"
                assert "message" in data
                assert "User logout processed" in data["message"]
                assert "data" in data
                assert isinstance(data["data"], dict)
                assert data["data"]["event"] == "SIGNED_OUT"
                assert data["data"]["user_id"] == "user-123"

    @pytest.mark.asyncio
    async def test_callback_endpoint_token_refreshed_event(self, client: TestClient) -> None:
        """Test callback endpoint for TOKEN_REFRESHED event with authenticated user."""
        # Mock the get_current_user dependency to return a user
        mock_user = self.create_mock_user()

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            with (
                patch("faster.core.auth.routers.extract_bearer_token_from_request", return_value="mock_token"),
                patch("faster.core.auth.routers.blacklist_delete", new_callable=AsyncMock) as mock_blacklist_delete,
            ):
                mock_blacklist_delete.return_value = None

                # Test TOKEN_REFRESHED event
                response = client.post("/auth/callback/TOKEN_REFRESHED")

                # Check that it's a JSON response
                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "application/json"

                # Parse the JSON response
                data = response.json()

                # Check the response structure
                assert "status" in data
                assert data["status"] == "success"
                assert "message" in data
                assert "Token refresh processed" in data["message"]
                assert "data" in data
                assert isinstance(data["data"], dict)
                assert data["data"]["event"] == "TOKEN_REFRESHED"
                assert data["data"]["user_id"] == "user-123"

    @pytest.mark.asyncio
    async def test_callback_endpoint_user_updated_event(self, client: TestClient) -> None:
        """Test callback endpoint for USER_UPDATED event with authenticated user."""
        # Mock the get_current_user dependency to return a user
        mock_user = self.create_mock_user()

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            with (
                patch("faster.core.auth.routers.extract_bearer_token_from_request", return_value="mock_token"),
                patch(
    "faster.core.auth.services.AuthService.background_update_user_info", new_callable=AsyncMock
                ) as mock_bg_update,
            ):
                mock_bg_update.return_value = None

                # Test USER_UPDATED event
                response = client.post("/auth/callback/USER_UPDATED")

                # Check that it's a JSON response
                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "application/json"

                # Parse the JSON response
                data = response.json()

                # Check the response structure
                assert "status" in data
                assert data["status"] == "success"
                assert "message" in data
                assert "User update processed" in data["message"]
                assert "data" in data
                assert isinstance(data["data"], dict)
                assert data["data"]["event"] == "USER_UPDATED"
                assert data["data"]["user_id"] == "user-123"

    @pytest.mark.asyncio
    async def test_callback_endpoint_password_recovery_event(self, client: TestClient) -> None:
        """Test callback endpoint for PASSWORD_RECOVERY event with authenticated user."""
        # Mock the get_current_user dependency to return a user
        mock_user = self.create_mock_user()

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            # Test PASSWORD_RECOVERY event
            response = client.post("/auth/callback/PASSWORD_RECOVERY")

            # Check that it's a JSON response
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "application/json"

            # Parse the JSON response
            data = response.json()

            # Check the response structure
            assert "status" in data
            assert data["status"] == "success"
            assert "message" in data
            assert "Password recovery processed" in data["message"]
            assert "data" in data
            assert isinstance(data["data"], dict)
            assert data["data"]["event"] == "PASSWORD_RECOVERY"

    @pytest.mark.asyncio
    async def test_callback_endpoint_invalid_event(self, client: TestClient) -> None:
        """Test callback endpoint for invalid event."""
        # Mock the get_current_user dependency to return a user
        mock_user = self.create_mock_user()

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            # Test invalid event
            response = client.post("/auth/callback/INVALID_EVENT")

            # Check that it's a JSON response with error
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "application/json"

            # Parse the JSON response
            data = response.json()

            # Check the response structure
            assert "status" in data
            assert data["status"] == "failed"
            assert "message" in data
            assert "Invalid event type: INVALID_EVENT" in data["message"]

    @pytest.mark.asyncio
    async def test_callback_endpoint_non_authenticated_user(self, client: TestClient) -> None:
        """Test callback endpoint for non-authenticated user."""

        # Override the app's dependency to return None (no authenticated user)
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return None

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None

            # Test SIGNED_IN event without authentication
            response = client.post("/auth/callback/SIGNED_IN")

            # Should return 200 with failed status because authentication is required
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "application/json"

            data = response.json()
            assert data["status"] == "failed"
            assert "Authentication required" in data["message"]

    @pytest.mark.asyncio
    async def test_callback_endpoint_service_exception_handling(self, client: TestClient) -> None:
        """Test callback endpoint handles service exceptions gracefully."""
        # Mock the get_current_user dependency to return a user
        mock_user = self.create_mock_user()

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            with (
                patch("faster.core.auth.routers.extract_bearer_token_from_request", return_value="mock_token"),
                patch("faster.core.auth.routers.blacklist_delete", new_callable=AsyncMock) as mock_blacklist_delete,
            ):
                # Make blacklist_delete raise an exception
                mock_blacklist_delete.side_effect = Exception("Redis connection failed")

                # Test SIGNED_IN event with service exception
                response = client.post("/auth/callback/SIGNED_IN")

                # Should return 200 with failed status due to exception
                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "application/json"

                data = response.json()
                assert data["status"] == "failed"
                assert "Error processing event SIGNED_IN" in data["message"]
                assert "Redis connection failed" in data["data"]["error"]

    @pytest.mark.asyncio
    async def test_notification_endpoint_service_exception_handling(self, client: TestClient) -> None:
        """Test notification endpoint handles exceptions gracefully."""
        # Test INITIAL_SESSION event with mocked exception
        with patch("faster.core.auth.routers._handle_initial_session", new_callable=AsyncMock) as mock_handler:
            mock_handler.side_effect = Exception("Database connection failed")

            response = client.post("/auth/notification/INITIAL_SESSION")

            # Should return 200 with failed status due to exception
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "application/json"

            data = response.json()
            assert data["status"] == "failed"
            assert "Error processing event INITIAL_SESSION" in data["message"]
            assert "Database connection failed" in data["data"]["error"]

    @pytest.mark.asyncio
    async def test_public_notification_endpoint_valid_event(self, client: TestClient) -> None:
        """Test public notification endpoint for valid event."""
        # Test INITIAL_SESSION event (the only one allowed on public endpoint)
        response = client.post("/auth/notification/INITIAL_SESSION")

        # Check that it's a JSON response
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/json"

        # Parse the JSON response
        data = response.json()

        # Check the response structure
        assert "status" in data
        assert data["status"] == "success"
        assert "message" in data
        assert "data" in data
        assert isinstance(data["data"], dict)
        assert data["data"]["event"] == "INITIAL_SESSION"
        assert data["data"]["user_id"] is None  # Public endpoint doesn't have user

    @pytest.mark.asyncio
    async def test_public_notification_endpoint_invalid_event(self, client: TestClient) -> None:
        """Test public notification endpoint for invalid event."""
        # Test SIGNED_IN event (not allowed on public endpoint)
        response = client.post("/auth/notification/SIGNED_IN")

        # Check that it's a JSON response with error
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/json"

        # Parse the JSON response
        data = response.json()

        # Check the response structure
        assert "status" in data
        assert data["status"] == "failed"
        assert "message" in data
        assert "Event SIGNED_IN not allowed on public endpoint" in data["message"]

    @pytest.mark.asyncio
    async def test_public_notification_endpoint_unauthorized_event(self, client: TestClient) -> None:
        """Test public notification endpoint for event that requires authentication."""
        # Test TOKEN_REFRESHED event (not allowed on public endpoint)
        response = client.post("/auth/notification/TOKEN_REFRESHED")

        # Check that it's a JSON response with error
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/json"

        # Parse the JSON response
        data = response.json()

        # Check the response structure
        assert "status" in data
        assert data["status"] == "failed"
        assert "message" in data
        assert "Event TOKEN_REFRESHED not allowed on public endpoint" in data["message"]

    @pytest.mark.asyncio
    async def test_callback_endpoint_empty_event_parameter(self, client: TestClient) -> None:
        """Test callback endpoint with empty event parameter."""
        # Mock the get_current_user dependency to return a user
        mock_user = self.create_mock_user()

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            # Test with empty event parameter
            response = client.post("/auth/callback/")

            # Should return 404 as the route doesn't match
            assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_notification_endpoint_get_request(self, client: TestClient) -> None:
        """Test notification endpoint rejects GET requests."""
        # Test GET request to POST-only endpoint
        response = client.get("/auth/notification/INITIAL_SESSION")

        # Should return 405 Method Not Allowed
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    @pytest.mark.asyncio
    async def test_callback_endpoint_get_request(self, client: TestClient) -> None:
        """Test callback endpoint rejects GET requests."""
        # Test GET request to POST-only endpoint
        response = client.get("/auth/callback/SIGNED_IN")

        # Should return 405 Method Not Allowed
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    @pytest.mark.asyncio
    async def test_onboarding_endpoint_with_user_metadata(self, client: TestClient) -> None:
        """Test onboarding endpoint with user having metadata."""
        # Create mock user with metadata
        mock_user = UserProfileData(
            id="user-123",
            email="test@example.com",
            email_confirmed_at=None,
            phone=None,
            created_at=datetime(2023, 1, 1),
            updated_at=datetime(2023, 1, 1),
            last_sign_in_at=None,
            app_metadata={"avatar_url": "https://example.com/avatar.jpg"},
            user_metadata={"username": "testuser", "full_name": "Test User"},
            aud="test",
            role="authenticated",
        )

        # Override the app's dependency to return our mock user
        async def mock_dependency(request: Request) -> UserProfileData | None:
            return mock_user

        cast(FastAPI, client.app).dependency_overrides[get_current_user] = mock_dependency

        with patch("faster.core.auth.routers.get_current_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user

            # Mock the auth service singleton instance method
            with patch.object(AuthService.get_instance(), "check_user_onboarding_complete", new_callable=AsyncMock) as mock_check_onboarding:
                mock_check_onboarding.return_value = False

                # Make a request to the endpoint
                response = client.get("/auth/onboarding")

                # Check that it's a JSON response
                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "application/json"

                # Parse the JSON response
                data = response.json()

                # Check the response structure
                assert "status" in data
                assert data["status"] == "success"
                assert "message" in data
                assert "data" in data
                assert isinstance(data["data"], dict)
                assert data["data"]["user_id"] == "user-123"
                assert data["data"]["email"] == "test@example.com"
