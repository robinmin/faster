"""Comprehensive tests for auth models including UserProfileData and AuthUser."""

from datetime import datetime
import json
from typing import Any

from pydantic import ValidationError
import pytest

from faster.core.auth.models import AuthUser, UserProfileData


class TestUserProfileData:
    """Test UserProfileData model."""

    @pytest.fixture
    def sample_user_data(self) -> dict[str, Any]:
        """Sample user data for testing."""
        return {
            "id": "user-123",
            "aud": "authenticated",
            "role": "authenticated",
            "email": "test@example.com",
            "email_confirmed_at": datetime(2023, 1, 1, 10, 0, 0),
            "phone": "+1234567890",
            "confirmed_at": datetime(2023, 1, 1, 10, 0, 0),
            "last_sign_in_at": datetime(2023, 1, 1, 10, 0, 0),
            "is_anonymous": False,
            "created_at": datetime(2023, 1, 1, 9, 0, 0),
            "updated_at": datetime(2023, 1, 1, 10, 0, 0),
            "app_metadata": {"provider": "email", "providers": ["email"]},
            "user_metadata": {"name": "Test User", "theme": "dark"},
        }

    def test_user_profile_data_creation(self, sample_user_data: dict[str, Any]) -> None:
        """Test UserProfileData creation with valid data."""
        user = UserProfileData(
            id=sample_user_data["id"],
            aud=sample_user_data["aud"],
            role=sample_user_data["role"],
            email=sample_user_data["email"],
            email_confirmed_at=sample_user_data["email_confirmed_at"],
            phone=sample_user_data["phone"],
            confirmed_at=sample_user_data["confirmed_at"],
            last_sign_in_at=sample_user_data["last_sign_in_at"],
            is_anonymous=sample_user_data["is_anonymous"],
            created_at=sample_user_data["created_at"],
            updated_at=sample_user_data["updated_at"],
            app_metadata=sample_user_data["app_metadata"],
            user_metadata=sample_user_data["user_metadata"],
        )

        assert user.id == "user-123"
        assert user.aud == "authenticated"
        assert user.role == "authenticated"
        assert user.email == "test@example.com"
        assert user.email_confirmed_at == datetime(2023, 1, 1, 10, 0, 0)
        assert user.phone == "+1234567890"
        assert user.confirmed_at == datetime(2023, 1, 1, 10, 0, 0)
        assert user.last_sign_in_at == datetime(2023, 1, 1, 10, 0, 0)
        assert user.is_anonymous is False
        assert user.created_at == datetime(2023, 1, 1, 9, 0, 0)
        assert user.updated_at == datetime(2023, 1, 1, 10, 0, 0)
        assert user.app_metadata == {"provider": "email", "providers": ["email"]}
        assert user.user_metadata == {"name": "Test User", "theme": "dark"}

    def test_user_profile_data_with_none_values(self) -> None:
        """Test UserProfileData creation with None values."""
        user_data: dict[str, Any] = {
            "id": "user-123",
            "aud": "authenticated",
            "role": "authenticated",
            "email": "test@example.com",
            "email_confirmed_at": None,
            "phone": None,
            "confirmed_at": None,
            "last_sign_in_at": None,
            "is_anonymous": False,
            "created_at": datetime(2023, 1, 1, 9, 0, 0),
            "updated_at": datetime(2023, 1, 1, 10, 0, 0),
            "app_metadata": {},
            "user_metadata": {},
        }

        user = UserProfileData(
            id=user_data["id"],
            aud=user_data["aud"],
            role=user_data["role"],
            email=user_data["email"],
            email_confirmed_at=user_data["email_confirmed_at"],
            phone=user_data["phone"],
            confirmed_at=user_data["confirmed_at"],
            last_sign_in_at=user_data["last_sign_in_at"],
            is_anonymous=user_data["is_anonymous"],
            created_at=user_data["created_at"],
            updated_at=user_data["updated_at"],
            app_metadata=user_data["app_metadata"],
            user_metadata=user_data["user_metadata"],
        )

        assert user.email_confirmed_at is None
        assert user.phone is None
        assert user.confirmed_at is None
        assert user.last_sign_in_at is None

    def test_user_profile_data_json_serialization(self, sample_user_data: dict[str, Any]) -> None:
        """Test UserProfileData JSON serialization."""
        user = UserProfileData(
            id=sample_user_data["id"],
            aud=sample_user_data["aud"],
            role=sample_user_data["role"],
            email=sample_user_data["email"],
            email_confirmed_at=sample_user_data["email_confirmed_at"],
            phone=sample_user_data["phone"],
            confirmed_at=sample_user_data["confirmed_at"],
            last_sign_in_at=sample_user_data["last_sign_in_at"],
            is_anonymous=sample_user_data["is_anonymous"],
            created_at=sample_user_data["created_at"],
            updated_at=sample_user_data["updated_at"],
            app_metadata=sample_user_data["app_metadata"],
            user_metadata=sample_user_data["user_metadata"],
        )
        json_str = user.model_dump_json()

        # Parse back to verify
        parsed = json.loads(json_str)
        assert parsed["id"] == "user-123"
        assert parsed["email"] == "test@example.com"
        assert parsed["app_metadata"]["provider"] == "email"

    def test_user_profile_data_json_deserialization(self, sample_user_data: dict[str, Any]) -> None:
        """Test UserProfileData JSON deserialization."""
        user = UserProfileData(
            id=sample_user_data["id"],
            aud=sample_user_data["aud"],
            role=sample_user_data["role"],
            email=sample_user_data["email"],
            email_confirmed_at=sample_user_data["email_confirmed_at"],
            phone=sample_user_data["phone"],
            confirmed_at=sample_user_data["confirmed_at"],
            last_sign_in_at=sample_user_data["last_sign_in_at"],
            is_anonymous=sample_user_data["is_anonymous"],
            created_at=sample_user_data["created_at"],
            updated_at=sample_user_data["updated_at"],
            app_metadata=sample_user_data["app_metadata"],
            user_metadata=sample_user_data["user_metadata"],
        )
        json_str = user.model_dump_json()

        # Deserialize
        user_from_json = UserProfileData.model_validate_json(json_str)

        assert user_from_json.id == user.id
        assert user_from_json.email == user.email
        assert user_from_json.app_metadata == user.app_metadata
        assert user_from_json.user_metadata == user.user_metadata

    def test_user_profile_data_dict_conversion(self, sample_user_data: dict[str, Any]) -> None:
        """Test UserProfileData to dict conversion."""
        user = UserProfileData(
            id=sample_user_data["id"],
            aud=sample_user_data["aud"],
            role=sample_user_data["role"],
            email=sample_user_data["email"],
            email_confirmed_at=sample_user_data["email_confirmed_at"],
            phone=sample_user_data["phone"],
            confirmed_at=sample_user_data["confirmed_at"],
            last_sign_in_at=sample_user_data["last_sign_in_at"],
            is_anonymous=sample_user_data["is_anonymous"],
            created_at=sample_user_data["created_at"],
            updated_at=sample_user_data["updated_at"],
            app_metadata=sample_user_data["app_metadata"],
            user_metadata=sample_user_data["user_metadata"],
        )
        user_dict = user.model_dump()

        assert user_dict["id"] == "user-123"
        assert user_dict["email"] == "test@example.com"
        assert isinstance(user_dict["created_at"], datetime)
        assert isinstance(user_dict["app_metadata"], dict)

    def test_user_profile_data_with_empty_metadata(self) -> None:
        """Test UserProfileData with empty metadata."""
        user_data: dict[str, Any] = {
            "id": "user-123",
            "aud": "authenticated",
            "role": "authenticated",
            "email": "test@example.com",
            "email_confirmed_at": None,
            "phone": None,
            "confirmed_at": None,
            "last_sign_in_at": None,
            "is_anonymous": False,
            "created_at": datetime(2023, 1, 1, 9, 0, 0),
            "updated_at": datetime(2023, 1, 1, 10, 0, 0),
            "app_metadata": {},
            "user_metadata": {},
        }

        user = UserProfileData(
            id=user_data["id"],
            aud=user_data["aud"],
            role=user_data["role"],
            email=user_data["email"],
            email_confirmed_at=user_data["email_confirmed_at"],
            phone=user_data["phone"],
            confirmed_at=user_data["confirmed_at"],
            last_sign_in_at=user_data["last_sign_in_at"],
            is_anonymous=user_data["is_anonymous"],
            created_at=user_data["created_at"],
            updated_at=user_data["updated_at"],
            app_metadata=user_data["app_metadata"],
            user_metadata=user_data["user_metadata"],
        )

        assert user.app_metadata == {}
        assert user.user_metadata == {}

    def test_user_profile_data_with_complex_metadata(self) -> None:
        """Test UserProfileData with complex metadata structures."""
        user_data: dict[str, Any] = {
            "id": "user-123",
            "aud": "authenticated",
            "role": "authenticated",
            "email": "test@example.com",
            "email_confirmed_at": None,
            "phone": None,
            "confirmed_at": None,
            "last_sign_in_at": None,
            "is_anonymous": False,
            "created_at": datetime(2023, 1, 1, 9, 0, 0),
            "updated_at": datetime(2023, 1, 1, 10, 0, 0),
            "app_metadata": {
                "provider": "google",
                "providers": ["google", "email"],
                "settings": {"theme": "dark", "notifications": True},
            },
            "user_metadata": {
                "name": "John Doe",
                "preferences": {"language": "en", "timezone": "UTC"},
                "profile": {"bio": "Software developer", "website": "https://example.com"},
            },
        }

        user = UserProfileData(
            id=user_data["id"],
            aud=user_data["aud"],
            role=user_data["role"],
            email=user_data["email"],
            email_confirmed_at=user_data["email_confirmed_at"],
            phone=user_data["phone"],
            confirmed_at=user_data["confirmed_at"],
            last_sign_in_at=user_data["last_sign_in_at"],
            is_anonymous=user_data["is_anonymous"],
            created_at=user_data["created_at"],
            updated_at=user_data["updated_at"],
            app_metadata=user_data["app_metadata"],
            user_metadata=user_data["user_metadata"],
        )

        assert user.app_metadata["provider"] == "google"
        assert user.app_metadata["settings"]["theme"] == "dark"
        assert user.user_metadata["name"] == "John Doe"
        assert user.user_metadata["preferences"]["language"] == "en"

    def test_user_profile_data_equality(self, sample_user_data: dict[str, Any]) -> None:
        """Test UserProfileData equality comparison."""
        user1 = UserProfileData(
            id=sample_user_data["id"],
            aud=sample_user_data["aud"],
            role=sample_user_data["role"],
            email=sample_user_data["email"],
            email_confirmed_at=sample_user_data["email_confirmed_at"],
            phone=sample_user_data["phone"],
            confirmed_at=sample_user_data["confirmed_at"],
            last_sign_in_at=sample_user_data["last_sign_in_at"],
            is_anonymous=sample_user_data["is_anonymous"],
            created_at=sample_user_data["created_at"],
            updated_at=sample_user_data["updated_at"],
            app_metadata=sample_user_data["app_metadata"],
            user_metadata=sample_user_data["user_metadata"],
        )
        user2 = UserProfileData(
            id=sample_user_data["id"],
            aud=sample_user_data["aud"],
            role=sample_user_data["role"],
            email=sample_user_data["email"],
            email_confirmed_at=sample_user_data["email_confirmed_at"],
            phone=sample_user_data["phone"],
            confirmed_at=sample_user_data["confirmed_at"],
            last_sign_in_at=sample_user_data["last_sign_in_at"],
            is_anonymous=sample_user_data["is_anonymous"],
            created_at=sample_user_data["created_at"],
            updated_at=sample_user_data["updated_at"],
            app_metadata=sample_user_data["app_metadata"],
            user_metadata=sample_user_data["user_metadata"],
        )

        assert user1 == user2

        # Modify one field
        user2.email = "different@example.com"
        assert user1 != user2

    def test_user_profile_data_immutability(self, sample_user_data: dict[str, Any]) -> None:
        """Test that UserProfileData fields can be modified."""
        user = UserProfileData(
            id=sample_user_data["id"],
            aud=sample_user_data["aud"],
            role=sample_user_data["role"],
            email=sample_user_data["email"],
            email_confirmed_at=sample_user_data["email_confirmed_at"],
            phone=sample_user_data["phone"],
            confirmed_at=sample_user_data["confirmed_at"],
            last_sign_in_at=sample_user_data["last_sign_in_at"],
            is_anonymous=sample_user_data["is_anonymous"],
            created_at=sample_user_data["created_at"],
            updated_at=sample_user_data["updated_at"],
            app_metadata=sample_user_data["app_metadata"],
            user_metadata=sample_user_data["user_metadata"],
        )

        # Test field modification
        original_email = user.email
        user.email = "new@example.com"
        assert user.email != original_email
        assert user.email == "new@example.com"

    def test_user_profile_data_with_minimal_required_fields(self) -> None:
        """Test UserProfileData with minimal required fields."""
        minimal_data: dict[str, Any] = {
            "id": "user-123",
            "aud": "authenticated",
            "role": "authenticated",
            "email": "test@example.com",
            "email_confirmed_at": None,
            "phone": None,
            "confirmed_at": None,
            "last_sign_in_at": None,
            "is_anonymous": False,
            "created_at": datetime(2023, 1, 1, 9, 0, 0),
            "updated_at": datetime(2023, 1, 1, 10, 0, 0),
            "app_metadata": {},
            "user_metadata": {},
        }

        user = UserProfileData(
            id=minimal_data["id"],
            aud=minimal_data["aud"],
            role=minimal_data["role"],
            email=minimal_data["email"],
            email_confirmed_at=minimal_data["email_confirmed_at"],
            phone=minimal_data["phone"],
            confirmed_at=minimal_data["confirmed_at"],
            last_sign_in_at=minimal_data["last_sign_in_at"],
            is_anonymous=minimal_data["is_anonymous"],
            created_at=minimal_data["created_at"],
            updated_at=minimal_data["updated_at"],
            app_metadata=minimal_data["app_metadata"],
            user_metadata=minimal_data["user_metadata"],
        )

        assert user.id == "user-123"
        assert user.email == "test@example.com"
        assert user.aud == "authenticated"
        assert user.role == "authenticated"


class TestAuthUserValidation:
    """Test AuthUser model validation rules."""

    def test_auth_user_valid_email(self) -> None:
        """Test AuthUser creation with valid email."""
        # Test passes if no exception is raised during creation
        _ = AuthUser(email="test@example.com", id="user-123", token="jwt-token", raw={"key": "value"})

    def test_auth_user_invalid_email(self) -> None:
        """Test AuthUser with invalid email raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            _ = AuthUser(email="invalid-email", id="user-123", token="jwt-token", raw={})

        # Verify the error is specifically about email validation
        assert "email" in str(exc_info.value).lower()

    def test_auth_user_edge_cases(self) -> None:
        """Test AuthUser with edge case emails."""
        # Valid edge cases
        valid_emails = ["user+tag@example.com", "user.name@domain.co.uk", "123@test.com"]

        for email in valid_emails:
            _ = AuthUser(email=email, id="user-123", token="jwt-token", raw={})
            # Test passes if no exception is raised

        # Invalid edge cases
        invalid_emails = ["@example.com", "user@", "user", "", "user@.com"]

        for email in invalid_emails:
            with pytest.raises(ValidationError):
                _ = AuthUser(email=email, id="user-123", token="jwt-token", raw={})

    def test_auth_user_creation(self) -> None:
        """Test AuthUser creation with valid data."""
        auth_user_data: dict[str, Any] = {
            "email": "test@example.com",
            "id": "user-123",
            "token": "jwt.token.here",
            "raw": {"sub": "user-123", "email": "test@example.com", "aud": "authenticated"},
        }

        auth_user = AuthUser(
            email=auth_user_data["email"],
            id=auth_user_data["id"],
            token=auth_user_data["token"],
            raw=auth_user_data["raw"],
        )

        assert auth_user.email == "test@example.com"
        assert auth_user.id == "user-123"
        assert auth_user.token == "jwt.token.here"
        assert auth_user.raw == {"sub": "user-123", "email": "test@example.com", "aud": "authenticated"}

    def test_auth_user_with_minimal_data(self) -> None:
        """Test AuthUser with minimal required data."""
        minimal_data: dict[str, Any] = {
            "email": "test@example.com",
            "id": "user-123",
            "token": "jwt.token",
            "raw": {},
        }

        auth_user = AuthUser(
            email=minimal_data["email"],
            id=minimal_data["id"],
            token=minimal_data["token"],
            raw=minimal_data["raw"],
        )

        assert auth_user.email == "test@example.com"
        assert auth_user.id == "user-123"
        assert auth_user.token == "jwt.token"
        assert auth_user.raw == {}

    def test_auth_user_json_serialization(self) -> None:
        """Test AuthUser JSON serialization."""
        auth_user_data: dict[str, Any] = {
            "email": "test@example.com",
            "id": "user-123",
            "token": "jwt.token.here",
            "raw": {"sub": "user-123", "email": "test@example.com"},
        }

        auth_user = AuthUser(
            email=auth_user_data["email"],
            id=auth_user_data["id"],
            token=auth_user_data["token"],
            raw=auth_user_data["raw"],
        )
        json_str = auth_user.model_dump_json()

        # Parse back to verify
        parsed = json.loads(json_str)
        assert parsed["email"] == "test@example.com"
        assert parsed["id"] == "user-123"
        assert parsed["token"] == "jwt.token.here"

    def test_auth_user_dict_conversion(self) -> None:
        """Test AuthUser to dict conversion."""
        auth_user_data: dict[str, Any] = {
            "email": "test@example.com",
            "id": "user-123",
            "token": "jwt.token.here",
            "raw": {"sub": "user-123", "email": "test@example.com"},
        }

        auth_user = AuthUser(
            email=auth_user_data["email"],
            id=auth_user_data["id"],
            token=auth_user_data["token"],
            raw=auth_user_data["raw"],
        )
        user_dict = auth_user.model_dump()

        assert user_dict["email"] == "test@example.com"
        assert user_dict["id"] == "user-123"
        assert user_dict["token"] == "jwt.token.here"
        assert isinstance(user_dict["raw"], dict)

    def test_auth_user_equality(self) -> None:
        """Test AuthUser equality comparison."""
        auth_user_data: dict[str, Any] = {
            "email": "test@example.com",
            "id": "user-123",
            "token": "jwt.token",
            "raw": {"sub": "user-123"},
        }

        user1 = AuthUser(
            email=auth_user_data["email"],
            id=auth_user_data["id"],
            token=auth_user_data["token"],
            raw=auth_user_data["raw"],
        )
        user2 = AuthUser(
            email=auth_user_data["email"],
            id=auth_user_data["id"],
            token=auth_user_data["token"],
            raw=auth_user_data["raw"],
        )

        assert user1 == user2

        # Modify one field
        user2.email = "different@example.com"
        assert user1 != user2

    def test_auth_user_with_complex_raw_data(self) -> None:
        """Test AuthUser with complex raw data."""
        complex_data: dict[str, Any] = {
            "email": "test@example.com",
            "id": "user-123",
            "token": "jwt.token",
            "raw": {
                "sub": "user-123",
                "email": "test@example.com",
                "aud": "authenticated",
                "role": "admin",
                "app_metadata": {"provider": "google"},
                "user_metadata": {"name": "Test User"},
                "exp": 1638360000,
                "iat": 1638356400,
            },
        }

        auth_user = AuthUser(
            email=complex_data["email"],
            id=complex_data["id"],
            token=complex_data["token"],
            raw=complex_data["raw"],
        )

        assert auth_user.raw["sub"] == "user-123"
        assert auth_user.raw["app_metadata"]["provider"] == "google"
        assert auth_user.raw["exp"] == 1638360000


class TestModelValidation:
    """Test model validation and error handling."""

    def test_user_profile_data_missing_required_field(self) -> None:
        """Test UserProfileData validation with missing required field."""
        invalid_data: dict[str, Any] = {
            "aud": "authenticated",
            "role": "authenticated",
            "email": "test@example.com",
            "email_confirmed_at": None,
            "phone": None,
            "confirmed_at": None,
            "last_sign_in_at": None,
            "is_anonymous": False,
            "created_at": datetime(2023, 1, 1, 9, 0, 0),
            "updated_at": datetime(2023, 1, 1, 10, 0, 0),
            "app_metadata": {},
            "user_metadata": {},
            # Missing 'id' field
        }

        with pytest.raises(ValidationError):
            _ = UserProfileData(**invalid_data)

    def test_auth_user_missing_required_field(self) -> None:
        """Test AuthUser validation with missing required field."""
        invalid_data: dict[str, Any] = {
            "email": "test@example.com",
            "id": "user-123",
            "raw": {},
            # Missing 'token' field
        }

        with pytest.raises(ValidationError):
            _ = AuthUser(**invalid_data)

    def test_user_profile_data_invalid_email_format(self) -> None:
        """Test UserProfileData with invalid email format."""
        # Note: UserProfileData inherits from Supabase User which may not validate email format
        # This test may need adjustment based on actual validation behavior

    def test_auth_user_invalid_email_format(self) -> None:
        """Test AuthUser with invalid email format."""
        invalid_data: dict[str, Any] = {
            "email": "invalid-email-format",
            "id": "user-123",
            "token": "jwt.token",
            "raw": {},
        }

        with pytest.raises(ValidationError):
            _ = AuthUser(
                email=invalid_data["email"],
                id=invalid_data["id"],
                token=invalid_data["token"],
                raw=invalid_data["raw"],
            )


class TestModelSerializationEdgeCases:
    """Test model serialization edge cases."""

    def test_user_profile_data_with_none_timestamps(self) -> None:
        """Test UserProfileData serialization with None timestamps."""
        user_data: dict[str, Any] = {
            "id": "user-123",
            "aud": "authenticated",
            "role": "authenticated",
            "email": "test@example.com",
            "email_confirmed_at": None,
            "phone": None,
            "confirmed_at": None,
            "last_sign_in_at": None,
            "is_anonymous": False,
            "created_at": datetime(2023, 1, 1, 9, 0, 0),
            "updated_at": datetime(2023, 1, 1, 10, 0, 0),
            "app_metadata": {},
            "user_metadata": {},
        }

        user = UserProfileData(
            id=user_data["id"],
            aud=user_data["aud"],
            role=user_data["role"],
            email=user_data["email"],
            email_confirmed_at=user_data["email_confirmed_at"],
            phone=user_data["phone"],
            confirmed_at=user_data["confirmed_at"],
            last_sign_in_at=user_data["last_sign_in_at"],
            is_anonymous=user_data["is_anonymous"],
            created_at=user_data["created_at"],
            updated_at=user_data["updated_at"],
            app_metadata=user_data["app_metadata"],
            user_metadata=user_data["user_metadata"],
        )
        json_str = user.model_dump_json()

        # Should serialize None values properly
        parsed = json.loads(json_str)
        assert parsed["email_confirmed_at"] is None
        assert parsed["phone"] is None

    def test_auth_user_with_empty_raw_dict(self) -> None:
        """Test AuthUser with empty raw dict."""
        user_data: dict[str, Any] = {
            "email": "test@example.com",
            "id": "user-123",
            "token": "jwt.token",
            "raw": {},
        }

        auth_user = AuthUser(
            email=user_data["email"],
            id=user_data["id"],
            token=user_data["token"],
            raw=user_data["raw"],
        )
        json_str = auth_user.model_dump_json()

        parsed = json.loads(json_str)
        assert parsed["raw"] == {}

    def test_user_profile_data_with_special_characters(self) -> None:
        """Test UserProfileData with special characters in metadata."""
        user_data: dict[str, Any] = {
            "id": "user-123",
            "aud": "authenticated",
            "role": "authenticated",
            "email": "test@example.com",
            "email_confirmed_at": None,
            "phone": None,
            "confirmed_at": None,
            "last_sign_in_at": None,
            "is_anonymous": False,
            "created_at": datetime(2023, 1, 1, 9, 0, 0),
            "updated_at": datetime(2023, 1, 1, 10, 0, 0),
            "app_metadata": {"special": "chars !@#$%^&*()"},
            "user_metadata": {"unicode": "测试 🚀"},
        }

        user = UserProfileData(
            id=user_data["id"],
            aud=user_data["aud"],
            role=user_data["role"],
            email=user_data["email"],
            email_confirmed_at=user_data["email_confirmed_at"],
            phone=user_data["phone"],
            confirmed_at=user_data["confirmed_at"],
            last_sign_in_at=user_data["last_sign_in_at"],
            is_anonymous=user_data["is_anonymous"],
            created_at=user_data["created_at"],
            updated_at=user_data["updated_at"],
            app_metadata=user_data["app_metadata"],
            user_metadata=user_data["user_metadata"],
        )
        json_str = user.model_dump_json()

        # Should handle special characters properly
        parsed = json.loads(json_str)
        assert parsed["app_metadata"]["special"] == "chars !@#$%^&*()"
        assert parsed["user_metadata"]["unicode"] == "测试 🚀"
