# tests/core/test_auth_services.py

from jose import JWTError, jwt
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


class TestAuthServiceJWT:
    """Tests for JWT verification in AuthService."""

    def test_verify_jwt_success(self, auth_service: AuthService) -> None:
        """
        Tests that a valid JWT is decoded successfully.
        """
        # Arrange
        payload = {"sub": TEST_USER_ID, "email": "test@example.com"}
        token = jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHMS[0])

        # Act
        decoded_payload = auth_service.verify_jwt(token)

        # Assert
        assert decoded_payload["sub"] == TEST_USER_ID
        assert decoded_payload["email"] == "test@example.com"

    def test_verify_jwt_invalid_signature_raises_error(self, auth_service: AuthService):
        """
        Tests that a JWT with an invalid signature raises a JWTError.
        """
        # Arrange
        payload = {"sub": TEST_USER_ID}
        token = jwt.encode(payload, "wrong-secret", algorithm=TEST_ALGORITHMS[0])

        # Act & Assert
        with pytest.raises(JWTError):
            auth_service.verify_jwt(token)

    def test_verify_jwt_expired_signature_raises_error(self, auth_service: AuthService):
        """
        Tests that an expired JWT raises a JWTError.
        """
        # Arrange
        payload = {"sub": TEST_USER_ID, "exp": -1}  # Already expired
        token = jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHMS[0])

        # Act & Assert
        with pytest.raises(JWTError):
            auth_service.verify_jwt(token)

    def test_verify_jwt_wrong_algorithm_raises_error(self, auth_service: AuthService):
        """
        Tests that a JWT with a different algorithm than configured raises a JWTError.
        """
        # Arrange
        payload = {"sub": TEST_USER_ID}
        token = jwt.encode(payload, TEST_SECRET, algorithm="HS512")

        # Act & Assert
        with pytest.raises(JWTError):
            auth_service.verify_jwt(token)


@pytest.mark.asyncio
class TestAuthServiceRoles:
    """Tests for role and access control logic in AuthService."""

    async def test_get_roles_by_user_id_returns_correct_roles(self, auth_service: AuthService, mocker):
        """
        Tests that get_roles_by_user_id correctly fetches and returns a set of roles.
        """
        # Arrange
        mock_user2role_get = mocker.patch(
            "faster.core.auth.services.user2role_get",
            return_value=["admin", "editor"],
        )

        # Act
        roles = await auth_service.get_roles_by_user_id(TEST_USER_ID)

        # Assert
        mock_user2role_get.assert_awaited_once_with(TEST_USER_ID)
        assert roles == {"admin", "editor"}

    async def test_get_roles_by_user_id_returns_empty_set_for_no_roles(self, auth_service: AuthService, mocker):
        """
        Tests that get_roles_by_user_id returns an empty set if the user has no roles.
        """
        # Arrange
        mocker.patch("faster.core.auth.services.user2role_get", return_value=None)

        # Act
        roles = await auth_service.get_roles_by_user_id(TEST_USER_ID)

        # Assert
        assert roles == set()

    async def test_get_roles_by_user_id_returns_empty_set_for_empty_user_id(self, auth_service: AuthService):
        """
        Tests that get_roles_by_user_id returns an empty set if user_id is empty.
        """
        # Act
        roles = await auth_service.get_roles_by_user_id("")

        # Assert
        assert roles == set()

    async def test_get_roles_by_tags_returns_correct_roles(self, auth_service: AuthService, mocker):
        """
        Tests that get_roles_by_tags aggregates roles from multiple tags.
        """

        # Arrange
        async def tag_role_side_effect(tag):
            if tag == "protected":
                return ["admin"]
            if tag == "editor-content":
                return ["editor", "admin"]
            return None

        mock_tag2role_get = mocker.patch(
            "faster.core.auth.services.tag2role_get",
            side_effect=tag_role_side_effect,
        )

        # Act
        roles = await auth_service.get_roles_by_tags(["protected", "editor-content"])

        # Assert
        assert mock_tag2role_get.await_count == 2
        assert roles == {"admin", "editor"}

    async def test_get_roles_by_tags_returns_empty_set_for_no_tags(self, auth_service: AuthService):
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
        mocker,
        user_roles: set,
        required_roles: set,
        expected_result: bool,
    ):
        """
        Tests the access logic with various combinations of user and required roles.
        """
        # Arrange
        mocker.patch.object(auth_service, "get_roles_by_user_id", return_value=user_roles)
        mocker.patch.object(auth_service, "get_roles_by_tags", return_value=required_roles)

        # Act
        has_access = await auth_service.check_access(TEST_USER_ID, ["some-tag"])

        # Assert
        assert has_access is expected_result

    async def test_check_access_denies_if_no_required_roles(self, auth_service: AuthService, mocker):
        """
        Tests that access is denied if the endpoint has no required roles,
        regardless of user roles.
        """
        # Arrange
        mocker.patch.object(auth_service, "get_roles_by_user_id", return_value={"viewer"})
        mocker.patch.object(auth_service, "get_roles_by_tags", return_value=set())

        # Act
        has_access = await auth_service.check_access(TEST_USER_ID, ["public-tag"])

        # Assert
        assert has_access is False
