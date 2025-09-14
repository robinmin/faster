from typing import Any
from unittest.mock import AsyncMock

import pytest

from faster.core.auth.services import AuthService
from faster.core.exceptions import DBError

# Constants for testing
TEST_SECRET = "a_very_secret_key"
TEST_ALGORITHMS = ["HS256"]
TEST_USER_ID = "user-123"


@pytest.fixture
def auth_service() -> AuthService:
    """Fixture to create an AuthService instance for testing."""
    return AuthService(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="test-anon-key",
        supabase_service_key="test-service-key",
        supabase_jwks_url="https://test.supabase.co/.well-known/jwks.json",
        supabase_audience="test-audience",
        auto_refresh_jwks=True,
        jwks_cache_ttl_seconds=3600,
        user_cache_ttl_seconds=3600,
    )


@pytest.mark.asyncio
class TestAuthServiceRoles:
    """Tests for role and access control logic in AuthService."""

    async def test_get_roles_returns_correct_roles(self, auth_service: AuthService, mocker: Any) -> None:
        """
        Tests that get_roles correctly fetches and returns a set of roles.
        """
        # Arrange
        mock_user2role_get = mocker.patch(
            "faster.core.auth.services.user2role_get",
            return_value=["admin", "editor"],
        )

        # Act
        roles = set(await auth_service.get_roles(TEST_USER_ID))

        # Assert
        mock_user2role_get.assert_awaited_once_with(TEST_USER_ID)
        assert roles == {"admin", "editor"}

    async def test_get_roles_returns_empty_set_for_no_roles(self, auth_service: AuthService, mocker: Any) -> None:
        """
        Tests that get_roles returns an empty set if the user has no roles.
        """
        # Arrange
        mocker.patch("faster.core.auth.services.user2role_get", return_value=None)

        # Act
        roles = set(await auth_service.get_roles(TEST_USER_ID))

        # Assert
        assert roles == set()

    async def test_get_roles_returns_empty_set_for_empty_user_id(self, auth_service: AuthService) -> None:
        """
        Tests that get_roles returns an empty set if user_id is empty.
        """
        # Act
        roles = set(await auth_service.get_roles(""))

        # Assert
        assert roles == set()

    async def test_get_roles_by_tags_returns_correct_roles(self, auth_service: AuthService, mocker: Any) -> None:
        """
        Tests that get_roles_by_tags aggregates roles from multiple tags.
        """

        # Arrange
        async def sysmap_side_effect(category: str, left: str | None = None) -> dict[str, list[str]]:
            if left is None:  # Called for lazy initialization
                return {"protected": ["admin"], "editor-content": ["editor", "admin"]}
            return {}

        mock_sysmap_get = mocker.patch(
            "faster.core.auth.services.sysmap_get",
            side_effect=sysmap_side_effect,
        )

        # Act
        roles = await auth_service.get_roles_by_tags(["protected", "editor-content"])

        # Assert
        assert mock_sysmap_get.await_count == 1  # Only called once for lazy initialization
        assert roles == {"admin", "editor"}

        # Test that cache is used on subsequent calls
        roles2 = await auth_service.get_roles_by_tags(["protected"])
        assert mock_sysmap_get.await_count == 1  # Still only called once
        assert roles2 == {"admin"}

        # Test cache clearing
        auth_service.clear_tag_role_cache()
        assert not auth_service.is_tag_role_cache_initialized()

        # Test that cache is reloaded after clearing
        roles3 = await auth_service.get_roles_by_tags(["editor-content"])
        assert mock_sysmap_get.await_count == 2  # Called again after cache clear
        assert roles3 == {"editor", "admin"}

    async def test_get_roles_by_tags_returns_empty_set_for_no_tags(self, auth_service: AuthService) -> None:
        """
        Tests that get_roles_by_tags returns an empty set if no tags are provided.
        """
        # Act
        roles = await auth_service.get_roles_by_tags([])

        # Assert
        assert roles == set()


@pytest.mark.asyncio
class TestAuthServiceAccessCheck:
    """Tests for the check_access method in AuthService."""

    @pytest.mark.parametrize(
        "user_roles, required_roles, expected_result",
        [
            ({"admin"}, {"admin", "editor"}, True),  # User has one of the required roles
            ({"editor"}, {"admin", "editor"}, True),  # User has the other required role
            ({"admin", "viewer"}, {"admin"}, True),  # User has the exact required role
            ({"viewer"}, {"admin", "editor"}, False),  # User has no matching roles
            (set(), {"admin"}, False),  # User has no roles
            ({"admin"}, set(), False),  # Endpoint requires no roles
        ],
    )
    async def test_check_access_logic(
        self,
        auth_service: AuthService,
        mocker: Any,
        user_roles: set[str],
        required_roles: set[str],
        expected_result: bool,
    ) -> None:
        """
        Tests the access logic with various combinations of user and required roles.
        """
        # Arrange
        mocker.patch.object(auth_service, "get_roles", return_value=user_roles)
        mocker.patch.object(auth_service, "get_roles_by_tags", return_value=required_roles)

        # Act
        has_access = await auth_service.check_access(TEST_USER_ID, ["some-tag"])

        # Assert
        assert has_access is expected_result

    async def test_check_access_denies_if_no_required_roles(self, auth_service: AuthService, mocker: Any) -> None:
        """
        Tests that access is denied if the endpoint has no required roles,
        regardless of user roles.
        """
        # Arrange
        mocker.patch.object(auth_service, "get_roles", return_value={"viewer"})
        mocker.patch.object(auth_service, "get_roles_by_tags", return_value=set())

        # Act
        has_access = await auth_service.check_access(TEST_USER_ID, ["public-tag"])

        # Assert
        assert has_access is False


@pytest.mark.asyncio
class TestAuthServiceLogEvent:
    """Tests for the log_event method in AuthService."""

    async def test_log_event_success_with_minimal_params(self, auth_service: AuthService, mocker: Any) -> None:
        """
        Test that log_event successfully proxies to repository with minimal parameters.
        """
        # Arrange
        mock_repo_log_event = mocker.patch.object(
            auth_service._repository,  # type: ignore[reportPrivateUsage, unused-ignore]
            "log_event",
            return_value=True
        )

        # Act
        result = await auth_service.log_event(
            event_type="auth",
            event_name="login",
            event_source="supabase"
        )

        # Assert
        assert result is True
        mock_repo_log_event.assert_awaited_once_with(
            event_type="auth",
            event_name="login",
            event_source="supabase",
            user_auth_id=None,
            trace_id=None,
            session_id=None,
            ip_address=None,
            user_agent=None,
            client_info=None,
            referrer=None,
            country_code=None,
            city=None,
            timezone=None,
            event_payload=None,
            extra_metadata=None,
            session=None,
        )

    async def test_log_event_success_with_all_params(self, auth_service: AuthService, mocker: Any) -> None:
        """
        Test that log_event successfully proxies to repository with all parameters.
        """
        # Arrange
        mock_repo_log_event = mocker.patch.object(
            auth_service._repository,  # type: ignore[reportPrivateUsage, unused-ignore]
            "log_event",
            return_value=True
        )

        event_payload = {"provider": "google", "session_duration": 3600}
        extra_metadata = {"browser": "chrome", "version": "1.0.0"}

        # Act
        result = await auth_service.log_event(
            event_type="user_action",
            event_name="button_click",
            event_source="frontend",
            user_auth_id="user123",
            trace_id="trace_abc",
            session_id="session_xyz",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0...",
            client_info="Chrome 91.0",
            referrer="https://example.com",
            country_code="US",
            city="San Francisco",
            timezone="PST",
            event_payload=event_payload,
            extra_metadata=extra_metadata
        )

        # Assert
        assert result is True
        mock_repo_log_event.assert_awaited_once_with(
            event_type="user_action",
            event_name="button_click",
            event_source="frontend",
            user_auth_id="user123",
            trace_id="trace_abc",
            session_id="session_xyz",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0...",
            client_info="Chrome 91.0",
            referrer="https://example.com",
            country_code="US",
            city="San Francisco",
            timezone="PST",
            event_payload=event_payload,
            extra_metadata=extra_metadata,
            session=None,
        )

    async def test_log_event_with_session_parameter(self, auth_service: AuthService, mocker: Any) -> None:
        """
        Test that log_event properly passes through session parameter.
        """
        # Arrange
        mock_repo_log_event = mocker.patch.object(
            auth_service._repository,  # type: ignore[reportPrivateUsage, unused-ignore]
            "log_event",
            return_value=True
        )
        mock_session = AsyncMock()

        # Act
        result = await auth_service.log_event(
            event_type="system",
            event_name="service_start",
            event_source="api",
            session=mock_session
        )

        # Assert
        assert result is True
        mock_repo_log_event.assert_awaited_once_with(
            event_type="system",
            event_name="service_start",
            event_source="api",
            user_auth_id=None,
            trace_id=None,
            session_id=None,
            ip_address=None,
            user_agent=None,
            client_info=None,
            referrer=None,
            country_code=None,
            city=None,
            timezone=None,
            event_payload=None,
            extra_metadata=None,
            session=mock_session,
        )

    async def test_log_event_handles_repository_value_error(self, auth_service: AuthService, mocker: Any) -> None:
        """
        Test that log_event returns False on ValueError from repository without raising exceptions.
        """
        # Arrange
        mocker.patch.object(
            auth_service._repository,  # type: ignore[reportPrivateUsage, unused-ignore]
            "log_event",
            side_effect=ValueError("Event type cannot be empty")
        )
        mock_logger_error = mocker.patch("faster.core.auth.services.logger.error")

        # Act
        result = await auth_service.log_event(
            event_type="",
            event_name="login",
            event_source="supabase"
        )

        # Assert
        assert result is False  # Should return False instead of raising
        mock_logger_error.assert_called_once()
        assert "AuthService.log_event failed" in str(mock_logger_error.call_args)

    async def test_log_event_handles_repository_db_error(self, auth_service: AuthService, mocker: Any) -> None:
        """
        Test that log_event returns False on DBError from repository without raising exceptions.
        """
        # Arrange
        db_error = DBError("Failed to log event auth/login: Database connection failed")
        mocker.patch.object(
            auth_service._repository,  # type: ignore[reportPrivateUsage, unused-ignore]
            "log_event",
            side_effect=db_error
        )
        mock_logger_error = mocker.patch("faster.core.auth.services.logger.error")

        # Act
        result = await auth_service.log_event(
            event_type="auth",
            event_name="login",
            event_source="supabase"
        )

        # Assert
        assert result is False  # Should return False instead of raising
        mock_logger_error.assert_called_once()
        assert "AuthService.log_event failed" in str(mock_logger_error.call_args)

    async def test_log_event_handles_generic_exception(self, auth_service: AuthService, mocker: Any) -> None:
        """
        Test that log_event returns False on generic exceptions without raising them.
        """
        # Arrange
        generic_error = RuntimeError("Unexpected error occurred")
        mocker.patch.object(
            auth_service._repository,  # type: ignore[reportPrivateUsage, unused-ignore]
            "log_event",
            side_effect=generic_error
        )
        mock_logger_error = mocker.patch("faster.core.auth.services.logger.error")

        # Act
        result = await auth_service.log_event(
            event_type="auth",
            event_name="login",
            event_source="supabase"
        )

        # Assert
        assert result is False  # Should return False instead of raising
        mock_logger_error.assert_called_once()
        assert "AuthService.log_event failed" in str(mock_logger_error.call_args)

    @pytest.mark.parametrize(
        "event_type, event_name, event_source, user_auth_id, expected_success",
        [
            # Valid cases
            ("auth", "login", "supabase", "user123", True),
            ("user_action", "click", "frontend", "user456", True),
            ("system", "startup", "api", None, True),  # Anonymous event
            ("navigation", "page_view", "frontend", "user789", True),
            # Repository returns False
            ("auth", "logout", "supabase", "user123", False),
        ],
    )
    async def test_log_event_parametrized_scenarios(
        self,
        auth_service: AuthService,
        mocker: Any,
        event_type: str,
        event_name: str,
        event_source: str,
        user_auth_id: str | None,
        expected_success: bool,
    ) -> None:
        """
        Test log_event with various parameter combinations using parametrization.
        """
        # Arrange
        mock_repo_log_event = mocker.patch.object(
            auth_service._repository,  # type: ignore[reportPrivateUsage, unused-ignore]
            "log_event",
            return_value=expected_success
        )

        # Act
        result = await auth_service.log_event(
            event_type=event_type,
            event_name=event_name,
            event_source=event_source,
            user_auth_id=user_auth_id
        )

        # Assert
        assert result is expected_success
        mock_repo_log_event.assert_awaited_once()

    async def test_log_event_with_complex_payload_data(self, auth_service: AuthService, mocker: Any) -> None:
        """
        Test log_event with complex nested payload and metadata.
        """
        # Arrange
        mock_repo_log_event = mocker.patch.object(
            auth_service._repository,  # type: ignore[reportPrivateUsage, unused-ignore]
            "log_event",
            return_value=True
        )

        complex_payload = {
            "user_action": {
                "button_id": "export_button",
                "page": "app_state",
                "coordinates": {"x": 100, "y": 200},
                "context": {
                    "previous_actions": ["page_load", "data_refresh"],
                    "session_time": 1800
                }
            },
            "performance": {
                "load_time": 250,
                "render_time": 150
            }
        }

        complex_metadata = {
            "system": {
                "version": "1.2.3",
                "environment": "production"
            },
            "analytics": {
                "experiment_id": "exp_123",
                "variant": "A"
            }
        }

        # Act
        result = await auth_service.log_event(
            event_type="user_action",
            event_name="complex_interaction",
            event_source="frontend",
            user_auth_id="user123",
            event_payload=complex_payload,
            extra_metadata=complex_metadata
        )

        # Assert
        assert result is True
        mock_repo_log_event.assert_awaited_once_with(
            event_type="user_action",
            event_name="complex_interaction",
            event_source="frontend",
            user_auth_id="user123",
            trace_id=None,
            session_id=None,
            ip_address=None,
            user_agent=None,
            client_info=None,
            referrer=None,
            country_code=None,
            city=None,
            timezone=None,
            event_payload=complex_payload,
            extra_metadata=complex_metadata,
            session=None,
        )
