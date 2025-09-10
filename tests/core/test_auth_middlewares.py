from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import Request, status
from fastapi.responses import JSONResponse
import pytest
from starlette.datastructures import Headers
from starlette.responses import Response

from faster.core.auth.middlewares import AuthMiddleware
from faster.core.auth.services import AuthService
from faster.core.models import AppResponse

# Constants
TEST_USER_ID = "user-123"
TEST_TOKEN = "valid.jwt.token"
TEST_EMAIL = "test@example.com"


@pytest.fixture
def mock_auth_service() -> MagicMock:
    """Fixture to create a mock AuthService."""
    service = MagicMock(spec=AuthService)
    service._auth_client = MagicMock()
    return service


@pytest.fixture
def mock_request() -> MagicMock:
    """Fixture to create a mock FastAPI Request object."""
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/protected/resource"
    request.headers = Headers({"Authorization": f"Bearer {TEST_TOKEN}"})
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

    @patch("faster.core.auth.middlewares.extract_bearer_token_from_request", return_value=TEST_TOKEN)
    async def test_middleware_success_for_protected_endpoint(
        self,
        mock_extract_token: MagicMock,
        middleware: AuthMiddleware,
        mock_request: MagicMock,
        mock_auth_service: MagicMock,
    ) -> None:
        """
        Tests that the middleware successfully processes a valid request
        for a protected endpoint.
        """

        # Arrange
        mock_user_profile = MagicMock()
        mock_user_profile.id = TEST_USER_ID
        mock_user_profile.email = TEST_EMAIL

        mock_auth_service.get_user_id_from_token = AsyncMock(return_value=TEST_USER_ID)
        mock_auth_service.get_user_by_id = AsyncMock(return_value=mock_user_profile)

        async def call_next(request: Request) -> Response:
            return JSONResponse({"status": "ok"}, status_code=200)

        # Act
        response = await middleware.dispatch(mock_request, call_next)

        # Assert
        mock_extract_token.assert_called_once_with(mock_request)
        mock_auth_service.get_user_id_from_token.assert_awaited_once_with(TEST_TOKEN)
        mock_auth_service.get_user_by_id.assert_awaited_once_with(TEST_USER_ID, from_cache=True)
        assert hasattr(mock_request.state, "user")
        assert mock_request.state.user.id == TEST_USER_ID
        assert mock_request.state.authenticated is True
        assert response.status_code == 200

    async def test_middleware_skips_public_endpoint(
        self,
        middleware: AuthMiddleware,
        mock_request: MagicMock,
        mock_auth_service: MagicMock,
    ) -> None:
        """
        Tests that the middleware skips authentication and authorization for
        endpoints tagged as 'public'.
        """
        # Arrange
        mock_request.url.path = "/public/resource"
        mock_request.app.state.endpoints = [
            {"path": "/protected/resource", "tags": ["protected"], "name": "test_endpoint", "methods": ["GET", "POST"]},
            {"path": "/public/resource", "tags": ["public"], "methods": ["GET"]},
        ]
        mock_auth_service._auth_client.get_user_id_from_token = AsyncMock()

        async def call_next(request: Request) -> Response:
            return JSONResponse({"status": "ok"}, status_code=200)

        # Act
        response = await middleware.dispatch(mock_request, call_next)

        # Assert
        mock_auth_service._auth_client.get_user_id_from_token.assert_not_awaited()
        assert response.status_code == 200

    async def test_middleware_allows_allowed_path(
        self,
        middleware: AuthMiddleware,
        mock_request: MagicMock,
        mock_auth_service: MagicMock,
    ) -> None:
        """
        Tests that the middleware allows requests to allowed paths.
        """
        # Arrange
        mock_request.url.path = "/docs"
        mock_auth_service._auth_client.get_user_id_from_token = AsyncMock()

        async def call_next(request: Request) -> Response:
            return JSONResponse({"status": "ok"}, status_code=200)

        # Act
        response = await middleware.dispatch(mock_request, call_next)

        # Assert
        mock_auth_service._auth_client.get_user_id_from_token.assert_not_awaited()
        assert mock_request.state.user is None
        assert mock_request.state.authenticated is False
        assert response.status_code == 200

    @patch("faster.core.auth.middlewares.extract_bearer_token_from_request", return_value=None)
    async def test_middleware_returns_401_if_no_auth_header(
        self, mock_extract_token: MagicMock, middleware: AuthMiddleware, mock_request: MagicMock
    ) -> None:
        """
        Tests that a 401 Unauthorized response is returned if the Authorization
        header is missing.
        """
        # Arrange
        mock_request.headers = Headers({})
        mock_request.app.state.endpoints = [
            {
                "path": "/protected/resource",
                "tags": ["protected"],
                "name": "test_endpoint",
                "methods": ["GET", "POST"],
            }
        ]

        async def call_next(request: Request) -> Response:
            return JSONResponse({"status": "ok"}, status_code=200)

        # Act
        response = await middleware.dispatch(mock_request, call_next)

        # Assert
        assert isinstance(response, AppResponse)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("faster.core.auth.middlewares.extract_bearer_token_from_request", return_value=TEST_TOKEN)
    async def test_middleware_returns_401_if_invalid_token(
        self,
        mock_extract_token: MagicMock,
        middleware: AuthMiddleware,
        mock_request: MagicMock,
        mock_auth_service: MagicMock,
    ) -> None:
        """
        Tests that a 401 Unauthorized response is returned if the JWT is invalid.
        """
        # Arrange
        mock_auth_service.get_user_id_from_token.return_value = None
        mock_request.app.state.endpoints = [
            {
                "path": "/protected/resource",
                "tags": ["protected"],
                "name": "test_endpoint",
                "methods": ["GET", "POST"],
            }
        ]

        async def call_next(request: Request) -> Response:
            return JSONResponse({"status": "ok"}, status_code=200)

        # Act
        response = await middleware.dispatch(mock_request, call_next)

        # Assert
        assert isinstance(response, AppResponse)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("faster.core.auth.middlewares.extract_bearer_token_from_request", return_value=TEST_TOKEN)
    async def test_middleware_returns_401_if_auth_fails(
        self,
        mock_extract_token: MagicMock,
        middleware: AuthMiddleware,
        mock_request: MagicMock,
        mock_auth_service: MagicMock,
    ) -> None:
        """
        Tests that a 401 Unauthorized response is returned if authentication fails.
        """
        # Arrange
        mock_auth_service.get_user_id_from_token.return_value = None
        mock_request.app.state.endpoints = [
            {
                "path": "/protected/resource",
                "tags": ["protected"],
                "name": "test_endpoint",
                "methods": ["GET", "POST"],
            }
        ]

        async def call_next(request: Request) -> Response:
            return JSONResponse({"status": "ok"}, status_code=200)

        # Act
        response = await middleware.dispatch(mock_request, call_next)

        # Assert
        assert isinstance(response, AppResponse)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_middleware_returns_404_if_endpoint_not_found(
        self, middleware: AuthMiddleware, mock_request: MagicMock
    ) -> None:
        """
        Tests that a 404 Not Found response is returned if the endpoint
        does not exist in the app's state.
        """
        # Arrange
        mock_request.url.path = "/nonexistent"
        mock_request.app.state.endpoints = []

        async def call_next(request: Request) -> Response:
            return JSONResponse({"status": "ok"}, status_code=200)

        # Act
        response = await middleware.dispatch(mock_request, call_next)

        # Assert
        assert isinstance(response, AppResponse)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_middleware_handles_exception_gracefully(
        self,
        middleware: AuthMiddleware,
        mock_request: MagicMock,
    ) -> None:
        """
        Tests that the middleware handles exceptions gracefully.
        """
        # Arrange
        mock_request.app.state.endpoints = [
            {
                "path": "/protected/resource",
                "tags": ["protected"],
                "name": "test_endpoint",
                "methods": ["GET", "POST"],
            }
        ]

        # Mock get_current_endpoint to raise an exception
        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "faster.core.auth.middlewares.get_current_endpoint", MagicMock(side_effect=Exception("Test error"))
            )

            async def call_next(request: Request) -> Response:
                return JSONResponse({"status": "ok"}, status_code=200)

            # Act
            response = await middleware.dispatch(mock_request, call_next)

        # Assert
        assert isinstance(response, AppResponse)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_middleware_with_prefix_allowed_paths(self) -> None:
        """
        Tests that the middleware correctly handles prefix allowed paths.
        """
        # Arrange
        mock_auth_service = MagicMock(spec=AuthService)
        mock_auth_service._auth_client = MagicMock()
        mock_user_profile = MagicMock()
        mock_user_profile.id = TEST_USER_ID
        mock_auth_service._auth_client.get_user_id_from_token = AsyncMock(return_value=mock_user_profile)

        app = MagicMock()
        middleware = AuthMiddleware(app, auth_service=mock_auth_service, allowed_paths=["/api/public/*"])

        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/api/public/resource"
        mock_request.headers = Headers({"Authorization": f"Bearer {TEST_TOKEN}"})
        mock_request.app.state.endpoints = [
            {
                "path": "/api/public/resource",
                "tags": ["protected"],
                "name": "test_endpoint",
                "methods": ["GET", "POST"],
            }
        ]
        mock_auth_service._auth_client.get_user_id_from_token = AsyncMock()

        async def call_next(request: Request) -> Response:
            return JSONResponse({"status": "ok"}, status_code=200)

        # Act
        response = await middleware.dispatch(mock_request, call_next)

        # Assert
        mock_auth_service._auth_client.get_user_id_from_token.assert_not_awaited()
        assert mock_request.state.user is None
        assert mock_request.state.authenticated is False
        assert response.status_code == 200
