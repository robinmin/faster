from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from faster.core.auth.models import AuthServiceConfig, RouterItem, UserProfileData
from faster.core.auth.services import AuthService
from faster.core.auth.utilities import log_event
from faster.core.config import Settings
from faster.core.exceptions import DBError

# Test constants
TEST_USER_ID = "test-user-123"
TEST_TOKEN = "valid.jwt.token"
TEST_EMAIL = "test@example.com"


@pytest.fixture
def mock_settings() -> Settings:
    """Mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.auth_enabled = True
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_anon_key = "test-anon-key"
    settings.supabase_service_key = "test-service-key"
    settings.supabase_jwks_url = "https://test.supabase.co/.well-known/jwks.json"
    settings.supabase_audience = "test-audience"
    settings.auto_refresh_jwks = True
    settings.jwks_cache_ttl_seconds = 3600
    settings.user_cache_ttl_seconds = 3600
    settings.is_debug = False
    return settings


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
def mock_auth_client() -> MagicMock:
    """Mock auth client for testing."""
    return MagicMock()


@pytest.fixture
def mock_repository() -> AsyncMock:
    """Mock repository for testing."""
    return AsyncMock()


@pytest.fixture
def auth_service(mock_settings: Settings) -> AuthService:
    """Create AuthService instance for testing."""
    with patch("faster.core.auth.services.AuthService.setup"):
        service = AuthService()
        return service


class TestAuthServiceInitialization:
    """Tests for AuthService initialization."""

    @pytest.mark.asyncio
    async def test_setup_success_with_auth_enabled(self, mock_settings: Settings) -> None:
        """Test successful setup with auth enabled."""
        service = AuthService()

        with patch("faster.core.auth.services.AuthProxy") as mock_auth_proxy:
            mock_auth_proxy.return_value = MagicMock()
            result = await service.setup(mock_settings)

            assert result is True
            # Test behavior instead of accessing private attributes
            health = await service.check_health()
            assert health["is_ready"] is True
            mock_auth_proxy.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_success_with_auth_disabled(self) -> None:
        """Test successful setup with auth disabled."""
        mock_settings = MagicMock(spec=Settings)
        mock_settings.auth_enabled = False
        # Provide all required attributes even when auth is disabled
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_anon_key = "test-anon-key"
        mock_settings.supabase_service_key = "test-service-key"
        mock_settings.supabase_jwks_url = "https://test.supabase.co/.well-known/jwks.json"
        mock_settings.supabase_audience = "test-audience"
        mock_settings.jwks_cache_ttl_seconds = 3600
        mock_settings.auto_refresh_jwks = True
        mock_settings.user_cache_ttl_seconds = 3600
        mock_settings.is_debug = False

        service = AuthService()
        result = await service.setup(mock_settings)

        assert result is True
        # Test behavior instead of accessing private attributes
        health = await service.check_health()
        assert health["auth_enabled"] is False

    @pytest.mark.asyncio
    async def test_setup_failure(self, mock_settings: Settings) -> None:
        """Test setup failure."""
        service = AuthService()

        with patch("faster.core.auth.services.AuthProxy", side_effect=Exception("Setup failed")):
            result = await service.setup(mock_settings)

            assert result is False
            # Test behavior instead of accessing private attributes
            health = await service.check_health()
            assert health["is_ready"] is False

    @pytest.mark.asyncio
    async def test_teardown_success(self, auth_service: AuthService) -> None:
        """Test successful teardown."""
        result = await auth_service.teardown()

        assert result is True
        # Test behavior instead of accessing private attributes
        health = await auth_service.check_health()
        assert health["is_ready"] is False


class TestAuthServiceHealthCheck:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_check_health_not_setup(self) -> None:
        """Test health check when service is not setup."""
        service = AuthService()

        result = await service.check_health()

        assert result["is_ready"] is False
        assert result["auth_enabled"] is False

    @pytest.mark.asyncio
    async def test_check_health_success(self, mock_settings: Settings, mock_auth_client: MagicMock) -> None:
        """Test successful health check."""
        # Create a fresh service and set it up properly
        service = AuthService()
        # Set up the config with the needed values
        test_config: AuthServiceConfig = {
            "auth_enabled": True,
            "supabase_url": "https://test.supabase.co",
            "supabase_anon_key": "test-anon-key",
            "supabase_service_key": "test-service-key",
            "supabase_jwks_url": "https://test.supabase.co/.well-known/jwks.json",
            "supabase_audience": "test-audience",
            "jwks_cache_ttl_seconds": 3600,
            "auto_refresh_jwks": True,
            "user_cache_ttl_seconds": 3600,
            "is_debug": False,
        }
        service.set_test_config(test_config)
        with (
            patch.object(service, "_auth_client", mock_auth_client),
            patch.object(service, "_is_setup", True),
            patch.object(mock_auth_client, "get_jwks_cache_info", return_value={"size": 10}),
        ):
            # Set tag-role cache directly since it's no longer managed externally
            service._router_info._tag_role_cache = {"admin": ["admin"], "user": ["user"]}  # type: ignore[reportPrivateUsage, unused-ignore]

            result = await service.check_health()
            assert result["is_ready"] is True
            assert result["auth_enabled"] is True
            assert result["tag_role_cache_size"] == 2
            assert result["jwks_cache"] == {"size": 10}

    @pytest.mark.asyncio
    async def test_check_health_with_error(self, mock_settings: Settings, mock_auth_client: MagicMock) -> None:
        """Test health check with error."""
        # Create a fresh service and set it up properly
        service = AuthService()
        # Set up the config with the needed values
        test_config: AuthServiceConfig = {
            "auth_enabled": True,
            "supabase_url": "https://test.supabase.co",
            "supabase_anon_key": "test-anon-key",
            "supabase_service_key": "test-service-key",
            "supabase_jwks_url": "https://test.supabase.co/.well-known/jwks.json",
            "supabase_audience": "test-audience",
            "jwks_cache_ttl_seconds": 3600,
            "auto_refresh_jwks": True,
            "user_cache_ttl_seconds": 3600,
            "is_debug": False,
        }
        service.set_test_config(test_config)
        with (
            patch.object(service, "_auth_client", mock_auth_client),
            patch.object(service, "_is_setup", True),
        ):
            result = await service.check_health()

            # Health check should still be ready since tag-role mapping errors are handled internally
            assert result["is_ready"] is True


class TestAuthServiceRouteManagement:
    """Tests for route management functionality."""

    @pytest.mark.asyncio
    async def test_refresh_data_replaces_collect_router_info(self, auth_service: AuthService) -> None:
        """Test refresh_data method (replacement for collect_router_info)."""

        mock_app = MagicMock()
        mock_route = MagicMock()
        mock_route.path = "/api/test"
        mock_route.methods = frozenset(["GET", "POST"])  # APIRoute uses frozenset
        mock_route.tags = ["protected"]
        mock_route.name = "test_endpoint"

        # Mock the endpoint function
        mock_endpoint = MagicMock()
        mock_endpoint.__name__ = "test_function"
        mock_route.endpoint = mock_endpoint

        mock_app.routes = [mock_route]

        # Patch isinstance to return True for our mock and mock sysmap_get
        with (
            patch("faster.core.auth.router_info.isinstance", return_value=True),
            patch("faster.core.auth.router_info.sysmap_get", new_callable=AsyncMock, return_value={}),
        ):
            router_items = await auth_service.refresh_data(mock_app)

        # Returns 2 RouterItems (one for each method)
        assert len(router_items) == 2

        # Check that we have both GET and POST endpoints
        methods = {item["method"] for item in router_items}
        assert methods == {"GET", "POST"}

        # Check common properties
        for item in router_items:
            assert item["path"] == "/api/test"
            assert item["tags"] == ["protected"]
            assert item["name"] == "test_endpoint"

    def test_find_route_success(self, auth_service: AuthService) -> None:
        """Test successful route finding."""
        mock_router_item: RouterItem = {
            "method": "GET",
            "path": "/api/test",
            "path_template": "/api/test",
            "name": "test",
            "tags": ["protected"],
            "allowed_roles": set(),
        }
        cache_key = "GET /api/test"
        mock_finder = MagicMock(return_value=cache_key)

        # Patch the RouterInfo's _route_finder and add item to cache
        with patch.object(auth_service._router_info, "_route_finder", mock_finder):  # type: ignore[reportPrivateUsage, unused-ignore]
            # Add RouterItem to cache
            auth_service._router_info._route_cache[cache_key] = mock_router_item  # type: ignore[reportPrivateUsage, unused-ignore]

            result = auth_service.find_route("GET", "/api/test")

            assert result is not None
            assert result["tags"] == ["protected"]
            mock_finder.assert_called_once_with("GET", "/api/test")

    def test_find_route_no_finder(self, auth_service: AuthService) -> None:
        """Test route finding when no finder is set."""
        # Patch the RouterInfo's _route_finder instead of AuthService's
        with patch.object(auth_service._router_info, "_route_finder", None):  # type: ignore[reportPrivateUsage, unused-ignore]
            result = auth_service.find_route("GET", "/api/test")

            assert result is None


class TestAuthServiceTagRoleMapping:
    """Tests for tag-role mapping functionality."""

    @pytest.mark.asyncio
    async def test_refresh_data(self, auth_service: AuthService) -> None:
        """Test refresh_data method."""
        mock_app = MagicMock()
        mock_route = MagicMock()
        mock_route.path = "/api/test"
        mock_route.methods = frozenset(["GET"])
        mock_route.tags = ["protected"]
        mock_route.name = "test_endpoint"

        mock_endpoint = MagicMock()
        mock_endpoint.__name__ = "test_function"
        mock_route.endpoint = mock_endpoint

        mock_app.routes = [mock_route]

        with (
            patch("faster.core.auth.router_info.isinstance", return_value=True),
            patch("faster.core.auth.router_info.sysmap_get", new_callable=AsyncMock, return_value={}),
        ):
            router_items = await auth_service.refresh_data(mock_app)

        assert len(router_items) == 1
        assert router_items[0]["method"] == "GET"
        assert router_items[0]["path"] == "/api/test"
        assert router_items[0]["tags"] == ["protected"]

        # Verify that route finder was created as part of refresh_data
        assert auth_service._router_info._route_finder is not None  # type: ignore[reportPrivateUsage, unused-ignore]

    @pytest.mark.asyncio
    async def test_get_router_item_via_router_info(self, auth_service: AuthService) -> None:
        """Test getting router item via RouterInfo instance."""
        # First refresh data to populate cache
        mock_app = MagicMock()
        mock_route = MagicMock()
        mock_route.path = "/api/test"
        mock_route.methods = frozenset(["GET"])
        mock_route.tags = ["test"]
        mock_route.name = "test_endpoint"

        mock_endpoint = MagicMock()
        mock_endpoint.__name__ = "test_function"
        mock_route.endpoint = mock_endpoint

        mock_app.routes = [mock_route]

        with (
            patch("faster.core.auth.router_info.isinstance", return_value=True),
            patch("faster.core.auth.router_info.sysmap_get", new_callable=AsyncMock, return_value={}),
        ):
            _ = await auth_service.refresh_data(mock_app)

        # Test getting router item via RouterInfo
        router_info = auth_service.get_router_info()
        router_item = router_info.get_router_item("GET", "/api/test")
        assert router_item is not None
        assert router_item["method"] == "GET"
        assert router_item["path"] == "/api/test"

        # Test getting non-existent router item
        missing_item = router_info.get_router_item("POST", "/api/missing")
        assert missing_item is None

    def test_get_router_info(self, auth_service: AuthService) -> None:
        """Test get_router_info method."""
        router_info = auth_service.get_router_info()

        # Should return the RouterInfo instance
        assert router_info is not None
        assert router_info == auth_service._router_info  # type: ignore[reportPrivateUsage, unused-ignore]


class TestAuthServiceUserManagement:
    """Tests for user management functionality."""

    @pytest.mark.asyncio
    async def test_get_user_by_id_from_cache(
        self, auth_service: AuthService, mock_user_profile: UserProfileData
    ) -> None:
        """Test getting user by ID from cache."""
        with patch("faster.core.auth.services.get_user_profile", return_value=mock_user_profile):
            result = await auth_service.get_user_by_id(TEST_USER_ID, from_cache=True)

            assert result == mock_user_profile

    @pytest.mark.asyncio
    async def test_get_user_by_id_from_database(
        self, auth_service: AuthService, mock_user_profile: UserProfileData, mock_repository: AsyncMock
    ) -> None:
        """Test getting user by ID from database."""
        with (
            patch("faster.core.auth.services.get_user_profile", return_value=None),
            patch.object(mock_repository, "get_user_info", return_value=mock_user_profile) as mock_get_db,
            patch("faster.core.auth.services.set_user_profile"),
            patch.object(auth_service, "_repository", mock_repository),
        ):
            result = await auth_service.get_user_by_id(TEST_USER_ID, from_cache=True)

            assert result == mock_user_profile
            _ = mock_get_db.assert_awaited_once_with(TEST_USER_ID, None)

    @pytest.mark.asyncio
    async def test_get_user_by_id_from_supabase(
        self,
        auth_service: AuthService,
        mock_user_profile: UserProfileData,
        mock_auth_client: MagicMock,
        mock_repository: AsyncMock,
    ) -> None:
        """Test getting user by ID from Supabase."""
        with (
            patch("faster.core.auth.services.get_user_profile", return_value=None),
            patch.object(mock_repository, "get_user_info", return_value=None),
            patch.object(
                mock_auth_client, "get_user_by_id", new_callable=AsyncMock, return_value=mock_user_profile
            ) as mock_get_supabase,
            patch.object(mock_repository, "set_user_info"),
            patch("faster.core.auth.services.set_user_profile"),
            patch.object(auth_service, "_repository", mock_repository),
            patch.object(auth_service, "_auth_client", mock_auth_client),
        ):
            result = await auth_service.get_user_by_id(TEST_USER_ID, from_cache=True)

            assert result == mock_user_profile
            mock_get_supabase.assert_awaited_once_with(TEST_USER_ID)

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(
        self, auth_service: AuthService, mock_auth_client: MagicMock, mock_repository: AsyncMock
    ) -> None:
        """Test getting user by ID when not found anywhere."""
        with (
            patch("faster.core.auth.services.get_user_profile", return_value=None),
            patch.object(mock_repository, "get_user_info", return_value=None),
            patch.object(mock_auth_client, "get_user_by_id", return_value=None),
            patch.object(auth_service, "_repository", mock_repository),
            patch.object(auth_service, "_auth_client", mock_auth_client),
        ):
            result = await auth_service.get_user_by_id(TEST_USER_ID, from_cache=True)

            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_token(
        self, auth_service: AuthService, mock_user_profile: UserProfileData, mock_auth_client: MagicMock
    ) -> None:
        """Test getting user by token."""
        with (
            patch.object(
                mock_auth_client, "get_user_by_token", new_callable=AsyncMock, return_value=mock_user_profile
            ) as mock_method,
            patch.object(auth_service, "_auth_client", mock_auth_client),
        ):
            result = await auth_service.get_user_by_token(TEST_TOKEN)

            assert result == mock_user_profile
            mock_method.assert_awaited_once_with(TEST_TOKEN)

    @pytest.mark.asyncio
    async def test_get_user_id_from_token(self, auth_service: AuthService, mock_auth_client: MagicMock) -> None:
        """Test getting user ID from token."""
        with (
            patch.object(
                mock_auth_client, "get_user_id_from_token", new_callable=AsyncMock, return_value=TEST_USER_ID
            ) as mock_method,
            patch.object(auth_service, "_auth_client", mock_auth_client),
        ):
            result = await auth_service.get_user_id_from_token(TEST_TOKEN)

            assert result == TEST_USER_ID
            mock_method.assert_awaited_once_with(TEST_TOKEN)


class TestAuthServiceRoleManagement:
    """Tests for role management functionality."""

    @pytest.mark.asyncio
    async def test_get_roles_from_cache(self, auth_service: AuthService) -> None:
        """Test getting roles from cache."""
        with patch("faster.core.auth.services.user2role_get", return_value=["admin", "user"]):
            result = await auth_service.get_roles(TEST_USER_ID, from_cache=True)

            assert result == ["admin", "user"]

    @pytest.mark.asyncio
    async def test_get_roles_from_database(self, auth_service: AuthService, mock_repository: AsyncMock) -> None:
        """Test getting roles from database."""
        with (
            patch("faster.core.auth.services.user2role_get", return_value=None),
            patch.object(mock_repository, "get_roles", return_value=["user"]) as mock_get_db,
            patch("faster.core.auth.services.user2role_set"),
            patch.object(auth_service, "_repository", mock_repository),
        ):
            result = await auth_service.get_roles(TEST_USER_ID, from_cache=True)

            assert result == ["user"]
            _ = mock_get_db.assert_awaited_once_with(TEST_USER_ID)

    @pytest.mark.asyncio
    async def test_get_roles_empty_user_id(self, auth_service: AuthService) -> None:
        """Test getting roles with empty user ID."""
        result = await auth_service.get_roles("", from_cache=True)

        assert result == []

    @pytest.mark.asyncio
    async def test_set_roles_success(self, auth_service: AuthService, mock_repository: AsyncMock) -> None:
        """Test setting roles successfully."""
        with (
            patch.object(mock_repository, "set_roles", return_value=True) as mock_set_db,
            patch("faster.core.auth.services.user2role_set", return_value=True),
            patch.object(auth_service, "_repository", mock_repository),
        ):
            result = await auth_service.set_roles(TEST_USER_ID, ["admin", "user"], to_cache=True)

            assert result is True
            _ = mock_set_db.assert_awaited_once_with(TEST_USER_ID, ["admin", "user"])

    @pytest.mark.asyncio
    async def test_set_roles_failure(self, auth_service: AuthService, mock_repository: AsyncMock) -> None:
        """Test setting roles failure."""
        with (
            patch.object(mock_repository, "set_roles", return_value=False),
            patch.object(auth_service, "_repository", mock_repository),
        ):
            result = await auth_service.set_roles(TEST_USER_ID, ["admin"], to_cache=True)

            assert result is False

    @pytest.mark.asyncio
    async def test_set_roles_empty_user_id(self, auth_service: AuthService) -> None:
        """Test setting roles with empty user ID."""
        result = await auth_service.set_roles("", ["admin"], to_cache=True)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_all_available_roles_success(self, auth_service: AuthService) -> None:
        """Test get_all_available_roles returns roles from sys_dict."""
        with patch("faster.core.auth.services.AppRepository") as mock_app_repository_class:
            # Mock AppRepository instance and its get_sys_dict method
            mock_app_repository = AsyncMock()
            mock_app_repository.get_sys_dict.return_value = {
                "user_role": {10: "default", 20: "developer", 30: "admin", 40: "moderator"}
            }
            mock_app_repository_class.return_value = mock_app_repository

            result = await auth_service.get_all_available_roles()

            # Should return sorted list of role values
            expected_roles = ["admin", "default", "developer", "moderator"]
            assert result == expected_roles

            # Verify AppRepository was called correctly
            mock_app_repository.get_sys_dict.assert_called_once_with(category="user_role")

    @pytest.mark.asyncio
    async def test_get_all_available_roles_empty_result(self, auth_service: AuthService) -> None:
        """Test get_all_available_roles handles empty sys_dict result."""
        with patch("faster.core.auth.services.AppRepository") as mock_app_repository_class:
            # Mock AppRepository instance returning empty result
            mock_app_repository = AsyncMock()
            mock_app_repository.get_sys_dict.return_value = {}
            mock_app_repository_class.return_value = mock_app_repository

            result = await auth_service.get_all_available_roles()

            # Should return empty list
            assert result == []

            # Verify AppRepository was called correctly
            mock_app_repository.get_sys_dict.assert_called_once_with(category="user_role")

    @pytest.mark.asyncio
    async def test_get_all_available_roles_db_error(self, auth_service: AuthService) -> None:
        """Test get_all_available_roles handles database errors."""
        with patch("faster.core.auth.services.AppRepository") as mock_app_repository_class:
            # Mock AppRepository instance raising DBError
            mock_app_repository = AsyncMock()
            mock_app_repository.get_sys_dict.side_effect = DBError("Database connection failed")
            mock_app_repository_class.return_value = mock_app_repository

            result = await auth_service.get_all_available_roles()

            # Should return empty list on error
            assert result == []

            # Verify AppRepository was called correctly
            mock_app_repository.get_sys_dict.assert_called_once_with(category="user_role")

    @pytest.mark.asyncio
    async def test_get_all_available_roles_unexpected_error(self, auth_service: AuthService) -> None:
        """Test get_all_available_roles handles unexpected errors."""
        with patch("faster.core.auth.services.AppRepository") as mock_app_repository_class:
            # Mock AppRepository instance raising unexpected error
            mock_app_repository = AsyncMock()
            mock_app_repository.get_sys_dict.side_effect = Exception("Unexpected error")
            mock_app_repository_class.return_value = mock_app_repository

            result = await auth_service.get_all_available_roles()

            # Should return empty list on error
            assert result == []

            # Verify AppRepository was called correctly
            mock_app_repository.get_sys_dict.assert_called_once_with(category="user_role")


class TestAuthServiceAccessControl:
    """Tests for access control functionality."""

    @pytest.mark.asyncio
    async def test_check_access_granted(self, auth_service: AuthService) -> None:
        """Test access granted."""
        user_roles: set[str] = {"admin"}
        allowed_roles: set[str] = {"admin"}
        result = await auth_service.check_access(user_roles, allowed_roles)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_access_denied_no_user_roles(self, auth_service: AuthService) -> None:
        """Test access denied when user has no roles."""
        user_roles: set[str] = set()  # Empty set - no roles
        allowed_roles: set[str] = {"admin"}
        result = await auth_service.check_access(user_roles, allowed_roles)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_access_denied_no_required_roles(self, auth_service: AuthService) -> None:
        """Test access denied when no required roles."""
        user_roles: set[str] = {"user"}
        allowed_roles: set[str] = set()  # Empty set - no required roles
        result = await auth_service.check_access(user_roles, allowed_roles)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_access_granted_multiple_roles(self, auth_service: AuthService) -> None:
        """Test access granted when user has multiple roles and one matches."""
        user_roles: set[str] = {"user", "admin", "moderator"}
        allowed_roles: set[str] = {"admin"}
        result = await auth_service.check_access(user_roles, allowed_roles)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_access_denied_role_mismatch(self, auth_service: AuthService) -> None:
        """Test access denied when user roles don't match required roles."""
        user_roles: set[str] = {"user", "guest"}
        allowed_roles: set[str] = {"admin", "moderator"}
        result = await auth_service.check_access(user_roles, allowed_roles)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_access_granted_partial_match(self, auth_service: AuthService) -> None:
        """Test access granted when user has one of multiple required roles."""
        user_roles: set[str] = {"user"}
        allowed_roles: set[str] = {"admin", "user"}
        result = await auth_service.check_access(user_roles, allowed_roles)

        assert result is True


class TestAuthServiceLoginLogout:
    """Tests for login/logout functionality."""

    @pytest.mark.asyncio
    async def test_process_user_login_success(
        self, auth_service: AuthService, mock_user_profile: UserProfileData
    ) -> None:
        """Test successful user login processing."""
        mock_user = MagicMock()
        with patch.object(auth_service, "_save_user_profile_to_database", return_value=mock_user) as mock_save:
            result = await auth_service.process_user_login(TEST_TOKEN, mock_user_profile)

            assert result == mock_user
            _ = mock_save.assert_awaited_once_with(mock_user_profile)

    @pytest.mark.asyncio
    async def test_process_user_login_failure(
        self, auth_service: AuthService, mock_user_profile: UserProfileData
    ) -> None:
        """Test user login processing failure."""
        with patch.object(auth_service, "_save_user_profile_to_database", side_effect=DBError("Save failed")):
            # Test that DBError is raised
            try:
                _ = await auth_service.process_user_login(TEST_TOKEN, mock_user_profile)
                raise AssertionError("Expected DBError to be raised")
            except DBError:
                pass  # Expected

    @pytest.mark.asyncio
    async def test_process_user_logout(self, auth_service: AuthService, mock_user_profile: UserProfileData) -> None:
        """Test user logout processing."""
        await auth_service.process_user_logout(TEST_TOKEN, mock_user_profile)

        # Should not raise any exceptions

    @pytest.mark.asyncio
    async def test_background_process_logout(
        self, auth_service: AuthService, mock_user_profile: UserProfileData
    ) -> None:
        """Test background logout processing."""
        with (
            patch("faster.core.auth.services.blacklist_add", return_value=True),
            patch.object(auth_service, "process_user_logout") as mock_process_logout,
        ):
            await auth_service.background_process_logout(TEST_TOKEN, mock_user_profile)

            _ = mock_process_logout.assert_awaited_once_with(TEST_TOKEN, mock_user_profile)


class TestAuthServiceUserProfilePersistence:
    """Tests for user profile persistence."""

    @pytest.mark.asyncio
    async def test_save_user_profile_to_database(
        self, auth_service: AuthService, mock_user_profile: UserProfileData, mock_repository: AsyncMock
    ) -> None:
        """Test saving user profile to database."""
        mock_user = MagicMock()
        with patch("faster.core.auth.services.get_transaction") as mock_transaction:
            mock_session = AsyncMock()
            mock_transaction.return_value.__aenter__.return_value = mock_session

            with (
                patch.object(mock_repository, "create_or_update_user", return_value=mock_user) as mock_create,
                patch.object(auth_service, "_repository", mock_repository),
                patch("faster.core.auth.services.set_user_profile"),
            ):
                # Test through process_user_login which calls _save_user_profile_to_database internally
                result = await auth_service.process_user_login(TEST_TOKEN, mock_user_profile)

                assert result is not None
                _ = mock_create.assert_awaited_once()
                args = mock_create.call_args[0]
                assert args[1]["id"] == TEST_USER_ID
                assert args[1]["email"] == TEST_EMAIL

    @pytest.mark.asyncio
    async def test_should_update_user_in_db_new_user(
        self, auth_service: AuthService, mock_user_profile: UserProfileData, mock_repository: AsyncMock
    ) -> None:
        """Test should update user in DB for new user."""
        with (
            patch.object(mock_repository, "should_update_user_in_db", return_value=True),
            patch.object(auth_service, "_repository", mock_repository),
        ):
            result = await auth_service.should_update_user_in_db(mock_user_profile)

            assert result is True

    @pytest.mark.asyncio
    async def test_should_update_user_in_db_old_update(
        self, auth_service: AuthService, mock_user_profile: UserProfileData, mock_repository: AsyncMock
    ) -> None:
        """Test should update user in DB for old update."""
        with (
            patch.object(mock_repository, "should_update_user_in_db", return_value=True),
            patch.object(auth_service, "_repository", mock_repository),
        ):
            result = await auth_service.should_update_user_in_db(mock_user_profile)

            assert result is True

    @pytest.mark.asyncio
    async def test_should_update_user_in_db_recent_update(
        self, auth_service: AuthService, mock_user_profile: UserProfileData, mock_repository: AsyncMock
    ) -> None:
        """Test should not update user in DB for recent update."""
        with (
            patch.object(mock_repository, "should_update_user_in_db", return_value=False),
            patch.object(auth_service, "_repository", mock_repository),
        ):
            result = await auth_service.should_update_user_in_db(mock_user_profile)

            assert result is False


class TestAuthServiceBackgroundTasks:
    """Tests for background task functionality."""

    @pytest.mark.asyncio
    async def test_background_update_user_info_success(
        self, auth_service: AuthService, mock_user_profile: UserProfileData
    ) -> None:
        """Test successful background user info update."""
        with patch("faster.core.auth.services.get_transaction") as mock_transaction:
            mock_session = AsyncMock()
            mock_transaction.return_value.__aenter__.return_value = mock_session

            with (
                patch.object(auth_service, "get_user_by_id", return_value=mock_user_profile),
                patch.object(auth_service, "_save_user_profile_to_database_with_session", create=True) as mock_save,
            ):
                await auth_service.background_update_user_info(TEST_TOKEN, TEST_USER_ID)

                _ = mock_save.assert_awaited_once_with(mock_session, mock_user_profile)

    @pytest.mark.asyncio
    async def test_background_update_user_info_no_user(self, auth_service: AuthService) -> None:
        """Test background user info update when user not found."""
        with patch.object(auth_service, "get_user_by_id", return_value=None):
            await auth_service.background_update_user_info(TEST_TOKEN, TEST_USER_ID)

            # Should not raise exception


class TestAuthServiceRepositoryProxy:
    """Tests for repository proxy methods."""

    @pytest.mark.asyncio
    async def test_check_user_onboarding_complete(self, auth_service: AuthService, mock_repository: AsyncMock) -> None:
        """Test checking user onboarding complete."""
        with (
            patch.object(mock_repository, "check_user_profile_exists", return_value=True) as mock_method,
            patch.object(auth_service, "_repository", mock_repository),
        ):
            result = await auth_service.check_user_onboarding_complete(TEST_USER_ID)

            assert result is True
            _ = mock_method.assert_awaited_once_with(TEST_USER_ID)

    @pytest.mark.asyncio
    async def test_get_user_by_auth_id(self, auth_service: AuthService, mock_repository: AsyncMock) -> None:
        """Test getting user by auth ID."""
        mock_user = MagicMock()
        with (
            patch.object(mock_repository, "get_user_by_auth_id_simple", return_value=mock_user),
            patch.object(auth_service, "_repository", mock_repository),
        ):
            result = await auth_service.get_user_by_auth_id(TEST_USER_ID)

            assert result == mock_user


class TestAuthServiceEventLogging:
    """Tests for event logging functionality."""

    @pytest.mark.asyncio
    async def test_log_event_success(self, auth_service: AuthService, mock_repository: AsyncMock) -> None:
        """Test successful event logging via utility function."""
        with (
            patch.object(mock_repository, "log_event", return_value=True) as mock_method,
            patch.object(auth_service, "_repository", mock_repository),
            patch.object(AuthService, "get_instance", return_value=auth_service),
        ):
            result = await log_event(
                event_type="auth", event_name="login", event_source="supabase", user_auth_id=TEST_USER_ID
            )

            assert result is True
            _ = mock_method.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_event_failure(self, auth_service: AuthService, mock_repository: AsyncMock) -> None:
        """Test event logging failure via utility function."""
        with (
            patch.object(mock_repository, "log_event", side_effect=Exception("Log failed")),
            patch.object(auth_service, "_repository", mock_repository),
            patch.object(AuthService, "get_instance", return_value=auth_service),
        ):
            result = await log_event(event_type="auth", event_name="login", event_source="supabase")

            assert result is False
