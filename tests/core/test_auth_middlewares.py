# tests/core/test_auth_middlewares.py
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
import pytest

from faster.core.auth.middlewares import AuthMiddleware, get_auth_user
from faster.core.auth.models import AuthUser
from faster.core.auth.services import AuthService

# Constants
TEST_USER_ID = "user-123"
TEST_TOKEN = "valid.jwt.token"
TEST_EMAIL = "test@example.com"


@pytest.fixture
def mock_auth_service() -> MagicMock:
    """Fixture to create a mock AuthService."""
    service = MagicMock(spec=AuthService)
    service.verify_jwt = MagicMock(return_value={"sub": TEST_USER_ID, "email": TEST_EMAIL})
    service.check_access = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_request() -> MagicMock:
    """Fixture to create a mock FastAPI Request object."""
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/protected/resource"
    request.headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    request.app.state.endpoints = [
        {
            "path": "/protected/resource",
            "tags": ["protected"],
            "name": "test_endpoint",
            "methods": ["GET", "POST"],
        }
    ]
    # Initialize request.state as a MagicMock that can have attributes set on it
    request.state = MagicMock()
    # Ensure 'auth_user' attribute does not exist initially
    del request.state.auth_user
    return request


@pytest.fixture
def middleware(mock_auth_service: MagicMock) -> AuthMiddleware:
    """Fixture to create an AuthMiddleware instance."""
    # A dummy app is sufficient for middleware testing
    app = MagicMock()
    return AuthMiddleware(app, auth_service=mock_auth_service)


@pytest.mark.asyncio
class TestAuthMiddleware:
    """Tests for the AuthMiddleware."""

    async def test_middleware_success_for_protected_endpoint(
        self, middleware: AuthMiddleware, mock_request: MagicMock, mock_auth_service: MagicMock
    ):
        """
        Tests that the middleware successfully processes a valid request
        for a protected endpoint.
        """

        # Arrange
        async def call_next(request):
            return JSONResponse({"status": "ok"}, status_code=200)

        # Act
        response = await middleware.dispatch(mock_request, call_next)

        # Assert
        mock_auth_service.verify_jwt.assert_called_once_with(TEST_TOKEN)
        mock_auth_service.check_access.assert_awaited_once_with(TEST_USER_ID, ["protected"])
        assert hasattr(mock_request.state, "auth_user")
        assert mock_request.state.auth_user.id == TEST_USER_ID
        assert response.status_code == 200

    async def test_middleware_skips_public_endpoint(
        self, middleware: AuthMiddleware, mock_request: MagicMock, mock_auth_service: MagicMock
    ):
        """
        Tests that the middleware skips authentication and authorization for
        endpoints tagged as 'public'.
        """
        # Arrange
        mock_request.url.path = "/public/resource"
        mock_request.app.state.endpoints.append({"path": "/public/resource", "tags": ["public"], "methods": ["GET"]})

        async def call_next(request):
            return JSONResponse({"status": "ok"}, status_code=200)

        # Act
        response = await middleware.dispatch(mock_request, call_next)

        # Assert
        mock_auth_service.verify_jwt.assert_not_called()
        mock_auth_service.check_access.assert_not_awaited()
        assert not hasattr(mock_request.state, "auth_user")
        assert response.status_code == 200

    async def test_middleware_returns_401_if_no_auth_header(self, middleware: AuthMiddleware, mock_request: MagicMock):
        """
        Tests that a 401 Unauthorized response is returned if the Authorization
        header is missing.
        """
        # Arrange
        mock_request.headers = {}

        # Act
        response = await middleware.dispatch(mock_request, MagicMock())

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Not authenticated" in response.body.decode()

    async def test_middleware_returns_401_if_invalid_token(
        self, middleware: AuthMiddleware, mock_request: MagicMock, mock_auth_service: MagicMock
    ):
        """
        Tests that a 401 Unauthorized response is returned if the JWT is invalid.
        """
        # Arrange
        mock_auth_service.verify_jwt.side_effect = Exception("Invalid signature")

        # Act
        response = await middleware.dispatch(mock_request, MagicMock())

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid token" in response.body.decode()

    async def test_middleware_returns_403_if_access_denied(
        self, middleware: AuthMiddleware, mock_request: MagicMock, mock_auth_service: MagicMock
    ):
        """
        Tests that a 403 Forbidden response is returned if the user lacks
        the required roles.
        """
        # Arrange
        mock_auth_service.check_access.return_value = False

        # Act
        response = await middleware.dispatch(mock_request, MagicMock())

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "insufficient role" in response.body.decode()

    async def test_middleware_returns_404_if_endpoint_not_found(
        self, middleware: AuthMiddleware, mock_request: MagicMock
    ):
        """
        Tests that a 404 Not Found response is returned if the endpoint
        does not exist in the app's state.
        """
        # Arrange
        mock_request.url.path = "/nonexistent"
        # Simulate endpoint not being found by returning an empty dict
        mock_request.app.state.endpoints = {}

        # Act
        response = await middleware.dispatch(mock_request, MagicMock())

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGetAuthUser:
    """Tests for the get_auth_user dependency."""

    def test_get_auth_user_success(self):
        """
        Tests that get_auth_user returns the user object if it exists on the
        request state.
        """
        # Arrange
        request = MagicMock(spec=Request)
        auth_user_obj = AuthUser(id=TEST_USER_ID, email=TEST_EMAIL, token=TEST_TOKEN, raw={})
        request.state.auth_user = auth_user_obj

        # Act
        user = get_auth_user(request)

        # Assert
        assert user == auth_user_obj

    def test_get_auth_user_raises_401_if_user_not_on_state(self):
        """
        Tests that get_auth_user raises a 401 HTTPException if the user
        object is not on the request state.
        """
        # Arrange
        request = MagicMock(spec=Request)
        # Ensure the attribute does not exist
        if hasattr(request.state, "auth_user"):
            delattr(request.state, "auth_user")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_auth_user(request)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
