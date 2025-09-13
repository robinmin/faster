from typing import Any

import pytest

from faster.core.auth.services import AuthService

# Constants for testing
TEST_SECRET = "a_very_secret_key"
TEST_ALGORITHMS = ["HS256"]
TEST_USER_ID = "user-123"


@pytest.fixture
def auth_service() -> AuthService:
    """Fixture to create an AuthService instance for testing."""
    return AuthService(jwt_secret=TEST_SECRET, algorithms=TEST_ALGORITHMS)


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
