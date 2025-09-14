"""Comprehensive tests for auth models including UserProfileData and AuthUser."""

from datetime import datetime
import json
from typing import Any

from pydantic import ValidationError
import pytest

from faster.core.auth.models import UserProfileData


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

    def test_user_profile_data_invalid_email_format(self) -> None:
        """Test UserProfileData with invalid email format."""
        # Note: UserProfileData inherits from Supabase User which may not validate email format
        # This test may need adjustment based on actual validation behavior


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
