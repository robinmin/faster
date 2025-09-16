"""Unit tests for new authentication utility functions."""

from faster.core.auth.utilities import (
    generate_trace_id,
    is_admin_role,
    mask_sensitive_data,
    sanitize_email,
    validate_password_strength,
    validate_role_name,
    validate_user_id,
)


class TestPasswordValidation:
    """Test password validation utilities."""

    def test_validate_password_strength_valid_password(self) -> None:
        """Test password validation with valid password."""
        password = "MyStr0ng!Pass"
        is_valid, errors = validate_password_strength(password)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_password_strength_empty_password(self) -> None:
        """Test password validation with empty password."""
        is_valid, errors = validate_password_strength("")

        assert is_valid is False
        assert "Password cannot be empty" in errors

    def test_validate_password_strength_none_password(self) -> None:
        """Test password validation with None password."""
        is_valid, errors = validate_password_strength(None)

        assert is_valid is False
        assert "Password cannot be empty" in errors

    def test_validate_password_strength_too_short(self) -> None:
        """Test password validation with too short password."""
        password = "Sh0rt!"
        is_valid, errors = validate_password_strength(password)

        assert is_valid is False
        assert "Password must be at least 8 characters long" in errors

    def test_validate_password_strength_no_uppercase(self) -> None:
        """Test password validation without uppercase letter."""
        password = "mystr0ng!pass"
        is_valid, errors = validate_password_strength(password)

        assert is_valid is False
        assert "Password must contain at least one uppercase letter" in errors

    def test_validate_password_strength_no_lowercase(self) -> None:
        """Test password validation without lowercase letter."""
        password = "MYSTR0NG!PASS"
        is_valid, errors = validate_password_strength(password)

        assert is_valid is False
        assert "Password must contain at least one lowercase letter" in errors

    def test_validate_password_strength_no_digit(self) -> None:
        """Test password validation without digit."""
        password = "MyStrong!Pass"
        is_valid, errors = validate_password_strength(password)

        assert is_valid is False
        assert "Password must contain at least one digit" in errors

    def test_validate_password_strength_no_special_char(self) -> None:
        """Test password validation without special character."""
        password = "MyStr0ngPass"
        is_valid, errors = validate_password_strength(password)

        assert is_valid is False
        assert "Password must contain at least one special character" in errors

    def test_validate_password_strength_multiple_errors(self) -> None:
        """Test password validation with multiple errors."""
        password = "weak"
        is_valid, errors = validate_password_strength(password)

        assert is_valid is False
        assert len(errors) == 4  # Too short, no uppercase, no digit, no special char

    def test_validate_password_strength_various_special_chars(self) -> None:
        """Test password validation with various special characters."""
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        for char in special_chars:
            password = f"MyStr0ng{char}Pass"
            is_valid, _ = validate_password_strength(password)
            assert is_valid is True, f"Password with '{char}' should be valid"


class TestEmailValidation:
    """Test email validation utilities."""

    def test_sanitize_email_valid(self) -> None:
        """Test email sanitization with valid email."""
        email = "Test@Example.Com"
        result = sanitize_email(email)

        assert result == "test@example.com"

    def test_sanitize_email_with_spaces(self) -> None:
        """Test email sanitization with spaces."""
        email = "  test@example.com  "
        result = sanitize_email(email)

        assert result == "test@example.com"

    def test_sanitize_email_empty(self) -> None:
        """Test email sanitization with empty email."""
        result = sanitize_email("")

        assert result is None

    def test_sanitize_email_none(self) -> None:
        """Test email sanitization with None email."""
        result = sanitize_email(None)

        assert result is None

    def test_sanitize_email_no_at_symbol(self) -> None:
        """Test email sanitization without @ symbol."""
        email = "testexample.com"
        result = sanitize_email(email)

        assert result is None

    def test_sanitize_email_no_domain(self) -> None:
        """Test email sanitization without domain."""
        email = "test@"
        result = sanitize_email(email)

        assert result is None

    def test_sanitize_email_no_local_part(self) -> None:
        """Test email sanitization without local part."""
        email = "@example.com"
        result = sanitize_email(email)

        assert result is None

    def test_sanitize_email_multiple_at_symbols(self) -> None:
        """Test email sanitization with multiple @ symbols."""
        email = "test@@example.com"
        result = sanitize_email(email)

        assert result is None

    def test_sanitize_email_no_dot_in_domain(self) -> None:
        """Test email sanitization without dot in domain."""
        email = "test@example"
        result = sanitize_email(email)

        assert result is None

    def test_sanitize_email_valid_complex(self) -> None:
        """Test email sanitization with complex valid email."""
        email = "User.Name+Tag@Example-Domain.CO.UK"
        result = sanitize_email(email)

        assert result == "user.name+tag@example-domain.co.uk"


class TestUserDataValidation:
    """Test user data validation utilities."""

    def test_validate_user_id_valid(self) -> None:
        """Test user ID validation with valid ID."""
        user_id = "user-123"
        result = validate_user_id(user_id)

        assert result is True

    def test_validate_user_id_valid_with_underscores(self) -> None:
        """Test user ID validation with underscores."""
        user_id = "user_123_test"
        result = validate_user_id(user_id)

        assert result is True

    def test_validate_user_id_valid_alphanumeric(self) -> None:
        """Test user ID validation with alphanumeric characters."""
        user_id = "user123ABC"
        result = validate_user_id(user_id)

        assert result is True

    def test_validate_user_id_empty(self) -> None:
        """Test user ID validation with empty ID."""
        result = validate_user_id("")

        assert result is False

    def test_validate_user_id_none(self) -> None:
        """Test user ID validation with None ID."""
        result = validate_user_id(None)

        assert result is False

    def test_validate_user_id_too_short(self) -> None:
        """Test user ID validation with too short ID."""
        user_id = "ab"
        result = validate_user_id(user_id)

        assert result is False

    def test_validate_user_id_too_long(self) -> None:
        """Test user ID validation with too long ID."""
        user_id = "a" * 256
        result = validate_user_id(user_id)

        assert result is False

    def test_validate_user_id_invalid_characters(self) -> None:
        """Test user ID validation with invalid characters."""
        user_id = "user@123"
        result = validate_user_id(user_id)

        assert result is False

    def test_validate_user_id_with_spaces(self) -> None:
        """Test user ID validation with spaces."""
        user_id = "user 123"
        result = validate_user_id(user_id)

        assert result is False

    def test_validate_role_name_valid(self) -> None:
        """Test role name validation with valid name."""
        role = "admin"
        result = validate_role_name(role)

        assert result is True

    def test_validate_role_name_valid_with_hyphens(self) -> None:
        """Test role name validation with hyphens."""
        role = "super-admin"
        result = validate_role_name(role)

        assert result is True

    def test_validate_role_name_valid_with_underscores(self) -> None:
        """Test role name validation with underscores."""
        role = "system_admin"
        result = validate_role_name(role)

        assert result is True

    def test_validate_role_name_empty(self) -> None:
        """Test role name validation with empty name."""
        result = validate_role_name("")

        assert result is False

    def test_validate_role_name_none(self) -> None:
        """Test role name validation with None name."""
        result = validate_role_name(None)

        assert result is False

    def test_validate_role_name_too_short(self) -> None:
        """Test role name validation with too short name."""
        role = "a"
        result = validate_role_name(role)

        assert result is False

    def test_validate_role_name_too_long(self) -> None:
        """Test role name validation with too long name."""
        role = "a" * 51
        result = validate_role_name(role)

        assert result is False

    def test_validate_role_name_invalid_characters(self) -> None:
        """Test role name validation with invalid characters."""
        role = "admin@role"
        result = validate_role_name(role)

        assert result is False


class TestSecurityUtilities:
    """Test security utility functions."""

    def test_mask_sensitive_data_default(self) -> None:
        """Test data masking with default visible characters."""
        data = "secretpassword123"
        result = mask_sensitive_data(data)

        assert result == "*************d123"
        assert len(result) == len(data)

    def test_mask_sensitive_data_custom_visible(self) -> None:
        """Test data masking with custom visible characters."""
        data = "secretpassword123"
        result = mask_sensitive_data(data, visible_chars=6)

        assert result == "***********ord123"
        assert len(result) == len(data)

    def test_mask_sensitive_data_short_data(self) -> None:
        """Test data masking with data shorter than visible chars."""
        data = "abc"
        result = mask_sensitive_data(data, visible_chars=4)

        assert result == "***"
        assert len(result) == len(data)

    def test_mask_sensitive_data_empty(self) -> None:
        """Test data masking with empty data."""
        result = mask_sensitive_data("")

        assert result == ""

    def test_mask_sensitive_data_exact_length(self) -> None:
        """Test data masking with data exactly visible chars length."""
        data = "1234"
        result = mask_sensitive_data(data, visible_chars=4)

        assert result == "****"

    def test_mask_sensitive_data_zero_visible(self) -> None:
        """Test data masking with zero visible characters."""
        data = "secret"
        result = mask_sensitive_data(data, visible_chars=0)

        assert result == "******secret"

    def test_generate_trace_id(self) -> None:
        """Test trace ID generation."""
        trace_id = generate_trace_id()

        assert isinstance(trace_id, str)
        assert len(trace_id) == 36  # Standard UUID format length
        assert trace_id.count("-") == 4  # Standard UUID has 4 hyphens

    def test_generate_trace_id_uniqueness(self) -> None:
        """Test that generated trace IDs are unique."""
        trace_ids = {generate_trace_id() for _ in range(100)}

        assert len(trace_ids) == 100  # All should be unique

    def test_is_admin_role_admin(self) -> None:
        """Test admin role detection with admin role."""
        assert is_admin_role("admin") is True

    def test_is_admin_role_super_admin(self) -> None:
        """Test admin role detection with super_admin role."""
        assert is_admin_role("super_admin") is True

    def test_is_admin_role_system_admin(self) -> None:
        """Test admin role detection with system_admin role."""
        assert is_admin_role("system_admin") is True

    def test_is_admin_role_root(self) -> None:
        """Test admin role detection with root role."""
        assert is_admin_role("root") is True

    def test_is_admin_role_case_insensitive(self) -> None:
        """Test admin role detection is case insensitive."""
        assert is_admin_role("ADMIN") is True
        assert is_admin_role("Admin") is True
        assert is_admin_role("aDmIn") is True

    def test_is_admin_role_non_admin(self) -> None:
        """Test admin role detection with non-admin roles."""
        assert is_admin_role("user") is False
        assert is_admin_role("moderator") is False
        assert is_admin_role("editor") is False
        assert is_admin_role("viewer") is False

    def test_is_admin_role_empty(self) -> None:
        """Test admin role detection with empty role."""
        assert is_admin_role("") is False

    def test_is_admin_role_similar_names(self) -> None:
        """Test admin role detection with similar but non-admin names."""
        assert is_admin_role("administrator") is False
        assert is_admin_role("admin_user") is False
        assert is_admin_role("user_admin") is False


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_validate_password_strength_unicode(self) -> None:
        """Test password validation with unicode characters."""
        password = "MyStr0ng!Pãss"  # Contains non-ASCII character
        is_valid, _ = validate_password_strength(password)

        assert is_valid is True

    def test_sanitize_email_unicode(self) -> None:
        """Test email sanitization with unicode characters."""
        email = "tëst@example.com"
        result = sanitize_email(email)

        assert result == "tëst@example.com"

    def test_validate_user_id_boundary_lengths(self) -> None:
        """Test user ID validation at boundary lengths."""
        # Exactly 3 characters (minimum)
        assert validate_user_id("abc") is True

        # Exactly 255 characters (maximum)
        user_id_255 = "a" * 255
        assert validate_user_id(user_id_255) is True

        # 256 characters (too long)
        user_id_256 = "a" * 256
        assert validate_user_id(user_id_256) is False

    def test_validate_role_name_boundary_lengths(self) -> None:
        """Test role name validation at boundary lengths."""
        # Exactly 2 characters (minimum)
        assert validate_role_name("ab") is True

        # Exactly 50 characters (maximum)
        role_50 = "a" * 50
        assert validate_role_name(role_50) is True

        # 51 characters (too long)
        role_51 = "a" * 51
        assert validate_role_name(role_51) is False

    def test_mask_sensitive_data_special_characters(self) -> None:
        """Test data masking with special characters."""
        data = "p@ssw0rd!#$"
        result = mask_sensitive_data(data)

        assert result == "*******d!#$"
        assert len(result) == len(data)
