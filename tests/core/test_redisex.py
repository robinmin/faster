import json
from unittest.mock import AsyncMock, patch

import pytest
from supabase_auth.types import User as UserProfile

from faster.core.redisex import (
    blacklist_add,
    blacklist_delete,
    blacklist_exists,
    get_jwks_key,
    get_user_profile,
    set_jwks_key,
    set_user_profile,
    tag2role_get,
    tag2role_set,
    user2role_get,
    user2role_set,
    userinfo_get,
    userinfo_set,
)


class TestBlacklistFunctions:
    """Test blacklist utility functions."""

    @pytest.mark.asyncio
    async def test_blacklist_add(self) -> None:
        """Test adding an item to the blacklist."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.set.return_value = True

            result = await blacklist_add("test-item", 3600)

            assert result is True
            mock_redis.set.assert_called_once_with("blacklist:test-item", "1", 3600)

    @pytest.mark.asyncio
    async def test_blacklist_add_without_expire(self) -> None:
        """Test adding an item to the blacklist without expiration."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.set.return_value = True

            result = await blacklist_add("test-item")

            assert result is True
            mock_redis.set.assert_called_once_with("blacklist:test-item", "1", None)

    @pytest.mark.asyncio
    async def test_blacklist_exists(self) -> None:
        """Test checking if an item is blacklisted."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.exists.return_value = 1

            result = await blacklist_exists("test-item")

            assert result is True
            mock_redis.exists.assert_called_once_with("blacklist:test-item")

    @pytest.mark.asyncio
    async def test_blacklist_exists_not_found(self) -> None:
        """Test checking if a non-existent item is blacklisted."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.exists.return_value = 0

            result = await blacklist_exists("test-item")

            assert result is False
            mock_redis.exists.assert_called_once_with("blacklist:test-item")

    @pytest.mark.asyncio
    async def test_blacklist_delete(self) -> None:
        """Test removing an item from the blacklist."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.delete.return_value = 1

            result = await blacklist_delete("test-item")

            assert result is True
            mock_redis.delete.assert_called_once_with("blacklist:test-item")


class TestUserInfoFunctions:
    """Test user info utility functions."""

    @pytest.mark.asyncio
    async def test_userinfo_get(self) -> None:
        """Test getting user information."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.get.return_value = "user-data"

            result = await userinfo_get("user-123")

            assert result == "user-data"
            mock_redis.get.assert_called_once_with("user:user-123")

    @pytest.mark.asyncio
    async def test_userinfo_get_none(self) -> None:
        """Test getting non-existent user information."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.get.return_value = None

            result = await userinfo_get("user-123")

            assert result == "None"  # The function converts None to string "None"
            mock_redis.get.assert_called_once_with("user:user-123")

    @pytest.mark.asyncio
    async def test_userinfo_set(self) -> None:
        """Test setting user information."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.set.return_value = True

            result = await userinfo_set("user-123", "user-data", 300)

            assert result is True
            mock_redis.set.assert_called_once_with("user:user-123", "user-data", 300)


class TestUserRoleFunctions:
    """Test user role utility functions."""

    @pytest.mark.asyncio
    async def test_user2role_get(self) -> None:
        """Test getting user roles."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.smembers.return_value = {"admin", "user"}

            result = await user2role_get("user-123")

            assert set(result) == {"admin", "user"}
            mock_redis.smembers.assert_called_once_with("user:user-123:role")

    @pytest.mark.asyncio
    async def test_user2role_get_empty(self) -> None:
        """Test getting user roles when none exist."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.smembers.return_value = set()

            result = await user2role_get("user-123")

            assert result == []
            mock_redis.smembers.assert_called_once_with("user:user-123:role")

    @pytest.mark.asyncio
    async def test_user2role_set(self) -> None:
        """Test setting user roles."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.sadd.return_value = 2

            result = await user2role_set("user-123", ["admin", "user"])

            assert result is True
            mock_redis.sadd.assert_called_once_with("user:user-123:role", "admin", "user")

    @pytest.mark.asyncio
    async def test_user2role_set_none(self) -> None:
        """Test removing user roles."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.delete.return_value = 1

            result = await user2role_set("user-123", None)

            assert result is True
            mock_redis.delete.assert_called_once_with("user:user-123:role")


class TestTagRoleFunctions:
    """Test tag role utility functions."""

    @pytest.mark.asyncio
    async def test_tag2role_get(self) -> None:
        """Test getting tag roles."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.smembers.return_value = {"admin", "moderator"}

            result = await tag2role_get("tag-important")

            assert set(result) == {"admin", "moderator"}
            mock_redis.smembers.assert_called_once_with("tag:tag-important:role")

    @pytest.mark.asyncio
    async def test_tag2role_get_empty(self) -> None:
        """Test getting tag roles when none exist."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.smembers.return_value = set()

            result = await tag2role_get("tag-important")

            assert result == []
            mock_redis.smembers.assert_called_once_with("tag:tag-important:role")

    @pytest.mark.asyncio
    async def test_tag2role_set(self) -> None:
        """Test setting tag roles."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.sadd.return_value = 2

            result = await tag2role_set("tag-important", ["admin", "moderator"])

            assert result is True
            mock_redis.sadd.assert_called_once_with("tag:tag-important:role", "admin", "moderator")

    @pytest.mark.asyncio
    async def test_tag2role_set_none(self) -> None:
        """Test removing tag roles."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.delete.return_value = 1

            result = await tag2role_set("tag-important", None)

            assert result is True
            mock_redis.delete.assert_called_once_with("tag:tag-important:role")


class TestAuthModuleFunctions:
    """Test auth module utility functions."""

    @pytest.mark.asyncio
    async def test_set_user_profile(self) -> None:
        """Test setting user profile."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.set.return_value = True

            # Create a mock user profile
            profile = UserProfile(
                id="user-123",
                email="test@example.com",
                email_confirmed_at=None,
                phone=None,
                created_at="2023-01-01T00:00:00Z",
                updated_at="2023-01-01T00:00:00Z",
                last_sign_in_at=None,
                app_metadata={},
                user_metadata={},
                aud="test",
                role="authenticated",
            )

            result = await set_user_profile("user-123", profile, 3600)

            assert result is True
            mock_redis.set.assert_called_once()
            args, kwargs = mock_redis.set.call_args
            assert args[0] == "user_profile:user-123"
            assert args[2] == 3600
            # Check that the data is JSON
            assert isinstance(args[1], str)
            json.loads(args[1])  # Should not raise

    @pytest.mark.asyncio
    async def test_get_user_profile(self) -> None:
        """Test getting user profile."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            # Create a mock user profile data
            profile_data = {
                "id": "user-123",
                "email": "test@example.com",
                "email_confirmed_at": None,
                "phone": None,
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
                "last_sign_in_at": None,
                "app_metadata": {},
                "user_metadata": {},
                "aud": "test",
                "role": "authenticated",
            }
            mock_redis.get.return_value = json.dumps(profile_data)

            result = await get_user_profile("user-123")

            assert result is not None
            assert isinstance(result, UserProfile)
            assert result.id == "user-123"
            assert result.email == "test@example.com"
            mock_redis.get.assert_called_once_with("user_profile:user-123")

    @pytest.mark.asyncio
    async def test_get_user_profile_none(self) -> None:
        """Test getting non-existent user profile."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.get.return_value = None

            result = await get_user_profile("user-123")

            assert result is None
            mock_redis.get.assert_called_once_with("user_profile:user-123")

    @pytest.mark.asyncio
    async def test_set_jwks_key(self) -> None:
        """Test setting JWKS key."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.set.return_value = True

            key_data = {"kid": "test-key", "alg": "RS256", "kty": "RSA"}

            result = await set_jwks_key("test-key", key_data, 3600)

            assert result is True
            mock_redis.set.assert_called_once()
            args, kwargs = mock_redis.set.call_args
            assert args[0] == "jwks_key:test-key"
            assert args[2] == 3600
            # Check that the data is JSON
            assert isinstance(args[1], str)
            json.loads(args[1])  # Should not raise

    @pytest.mark.asyncio
    async def test_get_jwks_key(self) -> None:
        """Test getting JWKS key."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            key_data = {"kid": "test-key", "alg": "RS256", "kty": "RSA"}
            mock_redis.get.return_value = json.dumps(key_data)

            result = await get_jwks_key("test-key")

            assert result is not None
            assert isinstance(result, dict)
            assert result["kid"] == "test-key"
            assert result["alg"] == "RS256"
            mock_redis.get.assert_called_once_with("jwks_key:test-key")

    @pytest.mark.asyncio
    async def test_get_jwks_key_none(self) -> None:
        """Test getting non-existent JWKS key."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.get.return_value = None

            result = await get_jwks_key("test-key")

            assert result is None
            mock_redis.get.assert_called_once_with("jwks_key:test-key")
