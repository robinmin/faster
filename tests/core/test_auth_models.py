"""Tests for auth models - focusing on custom validation rules only."""

from pydantic import ValidationError
import pytest

from faster.core.auth.models import AuthUser


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
