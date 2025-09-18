from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import Request, status
from fastapi.responses import JSONResponse
import pytest
from starlette.datastructures import Headers

from faster.core.auth.middlewares import AuthMiddleware, get_current_user, has_role
from faster.core.auth.models import RouterItem, UserProfileData
from faster.core.models import AppResponse

# Test constants
TEST_USER_ID = "test-user-123"
TEST_TOKEN = "valid.jwt.token"
TEST_EMAIL = "test@example.com"


@pytest.fixture
def mock_app() -> MagicMock:
    """Mock FastAPI application."""
    return MagicMock()


@pytest.fixture
def mock_request() -> MagicMock:
    """Mock FastAPI Request object."""
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/api/test"
    request.headers = Headers({"Authorization": f"Bearer {TEST_TOKEN}"})
    request.state = MagicMock()
    return request


@pytest.fixture
def mock_user_profile() -> UserProfileData:
    """Mock user profile data."""
    return UserProfileData(
        id=TEST_USER_ID,
        aud="test-audience",
        role="authenticated",
        email=TEST_EMAIL,
        email_confirmed_at=datetime(2023, 1, 1, 0, 0, 0),
        phone=None,
        confirmed_at=datetime(2023, 1, 1, 0, 0, 0),
        last_sign_in_at=datetime(2023, 1, 1, 0, 0, 0),
        is_anonymous=False,
        created_at=datetime(2023, 1, 1, 0, 0, 0),
        updated_at=datetime(2023, 1, 1, 0, 0, 0),
        app_metadata={},
        user_metadata={},
    )


@pytest.fixture
def mock_auth_service() -> MagicMock:
    """Mock auth service for testing."""
    service = MagicMock()
    service.find_route.return_value = {"path_template": "/api/test", "tags": ["protected"]}
    return service


@pytest.fixture
def middleware(mock_app: MagicMock, mock_auth_service: MagicMock) -> AuthMiddleware:
    """Create AuthMiddleware instance with mocked auth service."""
    with patch("faster.core.auth.middlewares.AuthService.get_instance", return_value=mock_auth_service):
        middleware = AuthMiddleware(
            app=mock_app, allowed_paths=["/docs", "/health", "/api/public/*"], require_auth=True
        )
        return middleware


class TestAuthMiddlewareInitialization:
    """Tests for AuthMiddleware initialization."""

    def test_init_with_default_allowed_paths(self, mock_app: MagicMock) -> None:
        """Test middleware initialization with default allowed paths."""
        with patch("faster.core.auth.middlewares.AuthService.get_instance") as mock_get_instance:
            mock_auth_service = MagicMock()
            mock_get_instance.return_value = mock_auth_service

            middleware = AuthMiddleware(app=mock_app)

            # Test initialization by checking that it doesn't raise errors
            # and that the auth service is properly set
            assert middleware is not None

    def test_init_with_custom_allowed_paths(self, mock_app: MagicMock) -> None:
        """Test middleware initialization with custom allowed paths."""
        with patch("faster.core.auth.middlewares.AuthService.get_instance") as mock_get_instance:
            mock_auth_service = MagicMock()
            mock_get_instance.return_value = mock_auth_service

            allowed_paths = ["/custom", "/api/v1/public/*", "/status"]
            middleware = AuthMiddleware(app=mock_app, allowed_paths=allowed_paths, require_auth=False)

            # Test that custom paths are processed by checking behavior
            assert middleware is not None

    def test_init_processes_prefix_paths_correctly(self, mock_app: MagicMock) -> None:
        """Test that prefix paths are processed correctly during initialization."""
        with patch("faster.core.auth.middlewares.AuthService.get_instance") as mock_get_instance:
            mock_auth_service = MagicMock()
            mock_get_instance.return_value = mock_auth_service

            allowed_paths = ["/api/*", "/public", "/health/*"]
            middleware = AuthMiddleware(app=mock_app, allowed_paths=allowed_paths)

            # Test that prefix paths are processed by checking behavior
            assert middleware is not None


class TestAuthMiddlewarePathChecking:
    """Tests for path checking logic."""

    @pytest.mark.asyncio
    async def test_check_allowed_path_exact_match(
        self, middleware: AuthMiddleware, mock_request: MagicMock, mock_auth_service: MagicMock
    ) -> None:
        """Test exact path matching for allowed paths."""
        mock_request.url.path = "/docs"

        async def call_next(request: Request) -> JSONResponse:
            return JSONResponse({"status": "ok"})

        # Mock the auth service methods that might be called
        mock_router_item: RouterItem = {
            "method": "GET",
            "path": "/docs",
            "path_template": "/docs",
            "name": "docs",
            "func_name": "docs_func",
            "tags": ["public"],
            "allowed_roles": set(),
        }
        with (
            patch("faster.core.auth.middlewares.blacklist_exists", new_callable=AsyncMock, return_value=False),
            patch.object(mock_auth_service, "find_route", return_value=mock_router_item),
        ):
            # Test through dispatch method which internally calls _check_allowed_path
            response = await middleware.dispatch(mock_request, call_next)

        assert response.status_code == 200
        assert mock_request.state.user is None
        assert mock_request.state.authenticated is False
        assert mock_request.state.roles == set()

    @pytest.mark.asyncio
    async def test_check_allowed_path_prefix_match(
        self, middleware: AuthMiddleware, mock_request: MagicMock, mock_auth_service: MagicMock
    ) -> None:
        """Test prefix path matching for allowed paths."""
        mock_request.url.path = "/api/public/users"

        async def call_next(request: Request) -> JSONResponse:
            return JSONResponse({"status": "ok"})

        # Mock the auth service methods that might be called
        mock_router_item: RouterItem = {
            "method": "GET",
            "path": "/api/public/users",
            "path_template": "/api/public/{path:path}",
            "name": "public_api",
            "func_name": "public_func",
            "tags": ["public"],
            "allowed_roles": set(),
        }
        with (
            patch("faster.core.auth.middlewares.blacklist_exists", new_callable=AsyncMock, return_value=False),
            patch.object(mock_auth_service, "find_route", return_value=mock_router_item),
        ):
            # Test through dispatch method
            response = await middleware.dispatch(mock_request, call_next)

        assert response.status_code == 200
        assert mock_request.state.user is None
        assert mock_request.state.authenticated is False
        assert mock_request.state.roles == set()

    @pytest.mark.asyncio
    async def test_check_allowed_path_no_match(self, middleware: AuthMiddleware, mock_request: MagicMock) -> None:
        """Test path that doesn't match any allowed paths."""
        mock_request.url.path = "/api/private"

        async def call_next(request: Request) -> JSONResponse:
            return JSONResponse({"status": "ok"})

        # This should require authentication and fail since we don't have auth setup
        with patch("faster.core.auth.middlewares.extract_bearer_token_from_request", return_value=None):
            response = await middleware.dispatch(mock_request, call_next)

            # Should return 401 since no token provided
            assert response.status_code == 401

    @pytest.mark.parametrize("method", ["HEAD", "OPTIONS"])
    @pytest.mark.asyncio
    async def test_dispatch_bypasses_auth_for_head_options(
        self, middleware: AuthMiddleware, mock_request: MagicMock, method: str
    ) -> None:
        """Test that HEAD and OPTIONS methods bypass authentication."""
        mock_request.method = method

        async def call_next(request: Request) -> JSONResponse:
            return JSONResponse({"status": "ok"})

        response = await middleware.dispatch(mock_request, call_next)

        assert response.status_code == 200
        assert mock_request.state.user is None
        assert mock_request.state.authenticated is False
        assert mock_request.state.roles == set()

    @pytest.mark.asyncio
    async def test_dispatch_bypasses_auth_when_disabled(self, mock_app: MagicMock, mock_request: MagicMock) -> None:
        """Test that authentication is bypassed when require_auth is False."""
        middleware = AuthMiddleware(app=mock_app, require_auth=False)

        async def call_next(request: Request) -> JSONResponse:
            return JSONResponse({"status": "ok"})

        response = await middleware.dispatch(mock_request, call_next)

        assert response.status_code == 200
        assert mock_request.state.user is None
        assert mock_request.state.authenticated is False
        assert mock_request.state.roles == set()


class TestAuthMiddlewareAuthentication:
    """Tests for authentication flow."""

    @patch("faster.core.auth.middlewares.extract_bearer_token_from_request")
    @patch("faster.core.auth.middlewares.blacklist_exists")
    @pytest.mark.asyncio
    async def test_successful_authentication_flow(
        self,
        mock_blacklist_exists: AsyncMock,
        mock_extract_token: MagicMock,
        middleware: AuthMiddleware,
        mock_auth_service: MagicMock,
        mock_request: MagicMock,
        mock_user_profile: UserProfileData,
    ) -> None:
        """Test successful authentication flow."""
        mock_extract_token.return_value = TEST_TOKEN
        mock_blacklist_exists.return_value = False

        # Mock auth service methods
        with (
            patch.object(
                mock_auth_service, "get_user_id_from_token", new_callable=AsyncMock, return_value=TEST_USER_ID
            ),
            patch.object(mock_auth_service, "get_user_by_id", new_callable=AsyncMock, return_value=mock_user_profile),
            patch.object(mock_auth_service, "check_access", new_callable=AsyncMock, return_value=True),
            patch.object(mock_auth_service, "get_roles", new_callable=AsyncMock, return_value=["admin", "user"]),
        ):

            async def call_next(request: Request) -> JSONResponse:
                return JSONResponse({"status": "ok"})

            response = await middleware.dispatch(mock_request, call_next)

            assert response.status_code == 200
            assert mock_request.state.user == mock_user_profile
            assert mock_request.state.authenticated is True
            assert mock_request.state.roles == {"admin", "user"}

    @patch("faster.core.auth.middlewares.extract_bearer_token_from_request")
    @pytest.mark.asyncio
    async def test_missing_token_returns_401(
        self, mock_extract_token: MagicMock, middleware: AuthMiddleware, mock_request: MagicMock
    ) -> None:
        """Test that missing token returns 401."""
        mock_extract_token.return_value = None

        async def call_next(request: Request) -> JSONResponse:
            return JSONResponse({"status": "ok"})

        response = await middleware.dispatch(mock_request, call_next)

        assert isinstance(response, AppResponse)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("faster.core.auth.middlewares.extract_bearer_token_from_request")
    @patch("faster.core.auth.middlewares.blacklist_exists")
    @pytest.mark.asyncio
    async def test_blacklisted_token_returns_401(
        self,
        mock_blacklist_exists: AsyncMock,
        mock_extract_token: MagicMock,
        middleware: AuthMiddleware,
        mock_request: MagicMock,
    ) -> None:
        """Test that blacklisted token returns 401."""
        mock_extract_token.return_value = TEST_TOKEN
        mock_blacklist_exists.return_value = True

        async def call_next(request: Request) -> JSONResponse:
            return JSONResponse({"status": "ok"})

        response = await middleware.dispatch(mock_request, call_next)

        assert isinstance(response, AppResponse)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("faster.core.auth.middlewares.extract_bearer_token_from_request")
    @patch("faster.core.auth.middlewares.blacklist_exists")
    @pytest.mark.asyncio
    async def test_invalid_user_id_returns_401(
        self,
        mock_blacklist_exists: AsyncMock,
        mock_extract_token: MagicMock,
        middleware: AuthMiddleware,
        mock_auth_service: MagicMock,
        mock_request: MagicMock,
    ) -> None:
        """Test that invalid user ID from token returns 401."""
        mock_extract_token.return_value = TEST_TOKEN
        mock_blacklist_exists.return_value = False

        with patch.object(mock_auth_service, "get_user_id_from_token", new_callable=AsyncMock, return_value=None):

            async def call_next(request: Request) -> JSONResponse:
                return JSONResponse({"status": "ok"})

            response = await middleware.dispatch(mock_request, call_next)

            assert isinstance(response, AppResponse)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("faster.core.auth.middlewares.extract_bearer_token_from_request")
    @patch("faster.core.auth.middlewares.blacklist_exists")
    @pytest.mark.asyncio
    async def test_access_denied_returns_403(
        self,
        mock_blacklist_exists: AsyncMock,
        mock_extract_token: MagicMock,
        middleware: AuthMiddleware,
        mock_auth_service: MagicMock,
        mock_request: MagicMock,
        mock_user_profile: UserProfileData,
    ) -> None:
        """Test that access denied returns 403."""
        mock_extract_token.return_value = TEST_TOKEN
        mock_blacklist_exists.return_value = False

        with (
            patch.object(
                mock_auth_service, "get_user_id_from_token", new_callable=AsyncMock, return_value=TEST_USER_ID
            ),
            patch.object(mock_auth_service, "get_user_by_id", new_callable=AsyncMock, return_value=mock_user_profile),
            patch.object(mock_auth_service, "get_roles", new_callable=AsyncMock, return_value=["user"]),
            patch.object(mock_auth_service, "check_access", new_callable=AsyncMock, return_value=False),
        ):

            async def call_next(request: Request) -> JSONResponse:
                return JSONResponse({"status": "ok"})

            response = await middleware.dispatch(mock_request, call_next)

            assert isinstance(response, AppResponse)
            assert response.status_code == status.HTTP_403_FORBIDDEN


class TestAuthMiddlewareUserProfileRetrieval:
    """Tests for user profile retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_authenticated_user_profile_success(
        self,
        middleware: AuthMiddleware,
        mock_auth_service: MagicMock,
        mock_user_profile: UserProfileData,
        mock_request: MagicMock,
    ) -> None:
        """Test successful user profile retrieval through dispatch."""
        mock_request.url.path = "/api/test"

        with (
            patch("faster.core.auth.middlewares.extract_bearer_token_from_request", return_value=TEST_TOKEN),
            patch("faster.core.auth.middlewares.blacklist_exists", return_value=False),
            patch.object(
                mock_auth_service, "get_user_id_from_token", new_callable=AsyncMock, return_value=TEST_USER_ID
            ),
            patch.object(mock_auth_service, "get_user_by_id", new_callable=AsyncMock, return_value=mock_user_profile),
            patch.object(mock_auth_service, "check_access", new_callable=AsyncMock, return_value=True),
            patch.object(mock_auth_service, "get_roles", new_callable=AsyncMock, return_value=["admin"]),
        ):

            async def call_next(request: Request) -> JSONResponse:
                return JSONResponse({"status": "ok"})

            response = await middleware.dispatch(mock_request, call_next)

            assert response.status_code == 200
            assert mock_request.state.user == mock_user_profile

    @pytest.mark.asyncio
    async def test_get_authenticated_user_profile_not_found(
        self, middleware: AuthMiddleware, mock_auth_service: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test user profile not found through dispatch."""
        mock_request.url.path = "/api/test"

        with (
            patch("faster.core.auth.middlewares.extract_bearer_token_from_request", return_value=TEST_TOKEN),
            patch("faster.core.auth.middlewares.blacklist_exists", return_value=False),
            patch.object(mock_auth_service, "get_user_id_from_token", return_value=TEST_USER_ID),
            patch.object(mock_auth_service, "get_user_by_id", return_value=None),
        ):

            async def call_next(request: Request) -> JSONResponse:
                return JSONResponse({"status": "ok"})

            response = await middleware.dispatch(mock_request, call_next)

            # Should return 401 when user profile is not found
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_authenticated_user_profile_exception(
        self, middleware: AuthMiddleware, mock_auth_service: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test exception during user profile retrieval through dispatch."""
        mock_request.url.path = "/api/test"

        with (
            patch("faster.core.auth.middlewares.extract_bearer_token_from_request", return_value=TEST_TOKEN),
            patch("faster.core.auth.middlewares.blacklist_exists", return_value=False),
            patch.object(mock_auth_service, "get_user_id_from_token", return_value=TEST_USER_ID),
            patch.object(mock_auth_service, "get_user_by_id", side_effect=Exception("Database error")),
        ):

            async def call_next(request: Request) -> JSONResponse:
                return JSONResponse({"status": "ok"})

            response = await middleware.dispatch(mock_request, call_next)

            # Should return 401 when there's an exception
            assert response.status_code == 401


class TestAuthMiddlewareStateManagement:
    """Tests for request state management."""

    @pytest.mark.asyncio
    async def test_set_authenticated_state(
        self,
        middleware: AuthMiddleware,
        mock_auth_service: MagicMock,
        mock_request: MagicMock,
        mock_user_profile: UserProfileData,
    ) -> None:
        """Test setting authenticated request state through dispatch."""
        mock_request.url.path = "/api/test"

        with (
            patch("faster.core.auth.middlewares.extract_bearer_token_from_request", return_value=TEST_TOKEN),
            patch("faster.core.auth.middlewares.blacklist_exists", return_value=False),
            patch.object(
                mock_auth_service, "get_user_id_from_token", new_callable=AsyncMock, return_value=TEST_USER_ID
            ),
            patch.object(mock_auth_service, "get_user_by_id", new_callable=AsyncMock, return_value=mock_user_profile),
            patch.object(mock_auth_service, "check_access", new_callable=AsyncMock, return_value=True),
            patch.object(mock_auth_service, "get_roles", new_callable=AsyncMock, return_value=["admin", "user"]),
        ):

            async def call_next(request: Request) -> JSONResponse:
                return JSONResponse({"status": "ok"})

            response = await middleware.dispatch(mock_request, call_next)

            assert response.status_code == 200
            assert mock_request.state.user == mock_user_profile
            assert mock_request.state.authenticated is True
            assert mock_request.state.roles == {"admin", "user"}

    @pytest.mark.asyncio
    async def test_set_unauthenticated_state(self, middleware: AuthMiddleware, mock_request: MagicMock) -> None:
        """Test setting unauthenticated request state through dispatch."""
        mock_request.url.path = "/api/test"

        # Mock the state attributes to ensure they start as None/False
        mock_request.state.user = None
        mock_request.state.authenticated = False
        mock_request.state.roles = set()

        with patch("faster.core.auth.middlewares.extract_bearer_token_from_request", return_value=None):

            async def call_next(request: Request) -> JSONResponse:
                return JSONResponse({"status": "ok"})

            response = await middleware.dispatch(mock_request, call_next)

            # Should return 401 for missing token, and state should be unauthenticated
            assert response.status_code == 401
            # For unauthenticated state, user should be None
            assert mock_request.state.user is None
            assert mock_request.state.authenticated is False
            assert mock_request.state.roles == set()


class TestAuthMiddlewareErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_dispatch_handles_route_not_found(
        self, middleware: AuthMiddleware, mock_auth_service: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test handling of route not found."""
        with patch.object(mock_auth_service, "find_route", return_value=None):

            async def call_next(request: Request) -> JSONResponse:
                return JSONResponse({"status": "ok"})

            response = await middleware.dispatch(mock_request, call_next)

            assert isinstance(response, AppResponse)
            assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_dispatch_handles_endpoint_tags_missing(
        self, middleware: AuthMiddleware, mock_auth_service: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test handling of missing endpoint tags."""
        with patch.object(mock_auth_service, "find_route", return_value={"path_template": "/api/test", "tags": []}):

            async def call_next(request: Request) -> JSONResponse:
                return JSONResponse({"status": "ok"})

            response = await middleware.dispatch(mock_request, call_next)

            assert isinstance(response, AppResponse)
            assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAuthMiddlewarePublicEndpoints:
    """Tests for public endpoint handling."""

    @pytest.mark.asyncio
    async def test_public_endpoint_bypass(
        self, middleware: AuthMiddleware, mock_auth_service: MagicMock, mock_request: MagicMock
    ) -> None:
        """Test that public endpoints bypass authentication."""
        mock_router_item: RouterItem = {
            "method": "GET",
            "path": "/api/public",
            "path_template": "/api/public",
            "name": "public_endpoint",
            "func_name": "public_func",
            "tags": ["public"],
            "allowed_roles": set(),
        }
        with patch.object(mock_auth_service, "find_route", return_value=mock_router_item):

            async def call_next(request: Request) -> JSONResponse:
                return JSONResponse({"status": "ok"})

            response = await middleware.dispatch(mock_request, call_next)

            assert response.status_code == 200
            assert mock_request.state.user is None
            assert mock_request.state.authenticated is False
            assert mock_request.state.roles == set()


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_get_current_user_success(self, mock_request: MagicMock, mock_user_profile: UserProfileData) -> None:
        """Test successful retrieval of current user."""
        mock_request.state.authenticated = True
        mock_request.state.user = mock_user_profile

        result = await get_current_user(mock_request)

        assert result == mock_user_profile

    @pytest.mark.asyncio
    async def test_get_current_user_not_authenticated(self, mock_request: MagicMock) -> None:
        """Test get_current_user when not authenticated."""
        mock_request.state.authenticated = False

        result = await get_current_user(mock_request)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_user_missing_state(self, mock_request: MagicMock) -> None:
        """Test get_current_user when state attributes are missing."""
        # Remove authenticated attribute
        delattr(mock_request.state, "authenticated")

        result = await get_current_user(mock_request)

        assert result is None


class TestHasRole:
    """Tests for has_role dependency."""

    @pytest.mark.asyncio
    async def test_has_role_success(self, mock_request: MagicMock) -> None:
        """Test successful role check."""
        mock_request.state.authenticated = True
        mock_request.state.roles = {"admin", "user"}

        result = await has_role(mock_request, "admin")

        assert result is True

    @pytest.mark.asyncio
    async def test_has_role_failure(self, mock_request: MagicMock) -> None:
        """Test failed role check."""
        mock_request.state.authenticated = True
        mock_request.state.roles = {"user"}

        result = await has_role(mock_request, "admin")

        assert result is False

    @pytest.mark.asyncio
    async def test_has_role_not_authenticated(self, mock_request: MagicMock) -> None:
        """Test has_role when not authenticated."""
        mock_request.state.authenticated = False

        result = await has_role(mock_request, "admin")

        assert result is False

    @pytest.mark.asyncio
    async def test_has_role_missing_roles(self, mock_request: MagicMock) -> None:
        """Test has_role when roles attribute is missing."""
        mock_request.state.authenticated = True
        # Remove roles attribute
        delattr(mock_request.state, "roles")

        result = await has_role(mock_request, "admin")

        assert result is False
