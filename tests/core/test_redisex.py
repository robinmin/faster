from datetime import datetime
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from faster.core.auth.models import UserProfileData
from faster.core.redisex import (
    MapCategory,
    blacklist_add,
    blacklist_delete,
    blacklist_exists,
    get_jwks_key,
    get_user_profile,
    set_jwks_key,
    set_user_profile,
    sysmap_get,
    sysmap_set,
    user2role_get,
    user2role_set,
)


class TestBlacklistFunctions:
    """Test blacklist utility functions."""

    @pytest.mark.asyncio
    async def test_blacklist_add(self) -> None:
        """Test adding an item to the blacklist."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.sadd.return_value = 1
            mock_redis.expire.return_value = True

            result = await blacklist_add("test-item", 3600)

            assert result is True
            mock_redis.sadd.assert_called_once_with("blacklist:token", "test-item")
            mock_redis.expire.assert_called_once_with("blacklist:token", 3600)

    @pytest.mark.asyncio
    async def test_blacklist_add_without_expire(self) -> None:
        """Test adding an item to the blacklist without expiration."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.sadd.return_value = 1
            mock_redis.expire.return_value = True

            result = await blacklist_add("test-item")

            assert result is True
            mock_redis.sadd.assert_called_once_with("blacklist:token", "test-item")
            mock_redis.expire.assert_called_once_with("blacklist:token", 3600)

    @pytest.mark.asyncio
    async def test_blacklist_exists(self) -> None:
        """Test checking if an item is blacklisted."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.sismember.return_value = True

            result = await blacklist_exists("test-item")

            assert result is True
            mock_redis.sismember.assert_called_once_with("blacklist:token", "test-item")

    @pytest.mark.asyncio
    async def test_blacklist_exists_not_found(self) -> None:
        """Test checking if a non-existent item is blacklisted."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.sismember.return_value = False

            result = await blacklist_exists("test-item")

            assert result is False
            mock_redis.sismember.assert_called_once_with("blacklist:token", "test-item")

    @pytest.mark.asyncio
    async def test_blacklist_delete(self) -> None:
        """Test removing an item from the blacklist."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.srem.return_value = 1

            result = await blacklist_delete("test-item")

            assert result is True
            mock_redis.srem.assert_called_once_with("blacklist:token", "test-item")


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
            mock_redis.smembers.assert_called_once_with("user:roles:user-123")

    @pytest.mark.asyncio
    async def test_user2role_get_empty(self) -> None:
        """Test getting user roles when none exist."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.smembers.return_value = set()

            result = await user2role_get("user-123")

            assert result == []
            mock_redis.smembers.assert_called_once_with("user:roles:user-123")

    @pytest.mark.asyncio
    async def test_user2role_set(self) -> None:
        """Test setting user roles."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.sadd.return_value = 2

            result = await user2role_set("user-123", ["admin", "user"])

            assert result is True
            mock_redis.sadd.assert_called_once_with("user:roles:user-123", "admin", "user")

    @pytest.mark.asyncio
    async def test_user2role_set_none(self) -> None:
        """Test removing user roles."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.delete.return_value = 1

            result = await user2role_set("user-123", None)

            assert result is True
            mock_redis.delete.assert_called_once_with("user:roles:user-123")


class TestSysmapFunctions:
    """Test system map utility functions for tag-role mappings."""

    @pytest.mark.asyncio
    async def test_sysmap_get_single_tag_roles(self) -> None:
        """Test getting single tag roles using sysmap_get."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.smembers.return_value = {"admin", "moderator"}

            result = await sysmap_get(str(MapCategory.TAG_ROLE), "tag-important")

            expected = {"tag-important": ["admin", "moderator"]}
            # Sort both lists for consistent comparison since sets don't guarantee order
            assert sorted(result["tag-important"]) == sorted(expected["tag-important"])
            mock_redis.smembers.assert_called_once_with("sys:map:tag_role:tag-important")

    @pytest.mark.asyncio
    async def test_sysmap_get_tag_roles_not_found(self) -> None:
        """Test getting tag roles when tag doesn't exist."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.smembers.return_value = set()  # Empty set

            result = await sysmap_get(str(MapCategory.TAG_ROLE), "tag-nonexistent")

            assert result == {}
            mock_redis.smembers.assert_called_once_with("sys:map:tag_role:tag-nonexistent")

    @pytest.mark.asyncio
    async def test_sysmap_set_tag_roles(self) -> None:
        """Test setting tag roles using sysmap_set."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            mapping = {
                "tag-important": ["admin", "moderator"],
                "tag-public": ["user"],
            }
            result = await sysmap_set(str(MapCategory.TAG_ROLE), mapping)

            assert result is True
            # Verify the keys are deleted first
            mock_redis.client.keys.assert_called_once_with("sys:map:tag_role:*")
            # Verify sadd is called for each left_value -> right_values mapping
            assert mock_redis.sadd.call_count == 2
            mock_redis.sadd.assert_any_call("sys:map:tag_role:tag-important", "admin", "moderator")
            mock_redis.sadd.assert_any_call("sys:map:tag_role:tag-public", "user")

    @pytest.mark.asyncio
    async def test_sysmap_set_multiple_right_values(self) -> None:
        """Test setting multiple right values for a left value using sysmap_set."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            mapping = {"tag-admin": ["read", "write", "delete"], "tag-user": ["read"], "tag-guest": ["read"]}
            result = await sysmap_set(str(MapCategory.TAG_ROLE), mapping)

            assert result is True
            # Verify the keys are deleted first
            mock_redis.client.keys.assert_called_once_with("sys:map:tag_role:*")
            # Verify sadd is called for each left_value -> right_values mapping
            assert mock_redis.sadd.call_count == 3
            mock_redis.sadd.assert_any_call("sys:map:tag_role:tag-admin", "read", "write", "delete")
            mock_redis.sadd.assert_any_call("sys:map:tag_role:tag-user", "read")
            mock_redis.sadd.assert_any_call("sys:map:tag_role:tag-guest", "read")

    @pytest.mark.asyncio
    async def test_sysmap_get_all_values(self) -> None:
        """Test getting all values in a category using sysmap_get with left=None."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            # Mock the keys and smembers calls
            mock_redis.client.keys.return_value = [
                b"sys:map:tag_role:tag-admin",
                b"sys:map:tag_role:tag-user",
                b"sys:map:tag_role:tag-guest",
            ]
            mock_redis.smembers.side_effect = [
                {"admin", "superuser"},  # for tag-admin
                {"user"},  # for tag-user
                {"guest"},  # for tag-guest
            ]

            result = await sysmap_get(str(MapCategory.TAG_ROLE))

            expected = {
                "tag-admin": ["admin", "superuser"],
                "tag-user": ["user"],
                "tag-guest": ["guest"],
            }
            # Sort lists for consistent comparison since sets don't guarantee order
            for key in expected:  # noqa: PLC0206
                if key in result:
                    result[key] = sorted(result[key])
                    expected[key] = sorted(expected[key])
            assert result == expected
            mock_redis.client.keys.assert_called_once_with("sys:map:tag_role:*")
            assert mock_redis.smembers.call_count == 3

    @pytest.mark.asyncio
    async def test_sysmap_get_all_values_empty(self) -> None:
        """Test getting all values when category is empty."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.client.keys.return_value = []

            result = await sysmap_get(str(MapCategory.TAG_ROLE))

            assert result == {}
            mock_redis.client.keys.assert_called_once_with("sys:map:tag_role:*")

    @pytest.mark.asyncio
    async def test_sysmap_get_all_values_complex(self) -> None:
        """Test getting all values with complex role mappings."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            # Mock the keys and smembers calls
            mock_redis.client.keys.return_value = [
                b"sys:map:tag_role:admin",
                b"sys:map:tag_role:user",
                b"sys:map:tag_role:guest",
            ]
            mock_redis.smembers.side_effect = [
                {"read", "write", "delete"},  # for admin
                {"read", "write"},  # for user
                {"read"},  # for guest
            ]

            result = await sysmap_get(str(MapCategory.TAG_ROLE))

            expected = {
                "admin": ["read", "write", "delete"],
                "user": ["read", "write"],
                "guest": ["read"],
            }
            # Sort lists for consistent comparison since sets don't guarantee order
            for key in expected:  # noqa: PLC0206
                if key in result:
                    result[key] = sorted(result[key])
                    expected[key] = sorted(expected[key])
            assert result == expected
            mock_redis.client.keys.assert_called_once_with("sys:map:tag_role:*")
            assert mock_redis.smembers.call_count == 3


class TestAuthModuleFunctions:
    """Test auth module utility functions."""

    @pytest.mark.asyncio
    async def test_set_user_profile(self) -> None:
        """Test setting user profile."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.set.return_value = True

            # Create a mock user profile object

            profile = UserProfileData(
                id="user-123",
                email="test@example.com",
                email_confirmed_at=None,
                phone=None,
                created_at=datetime.fromisoformat("2023-01-01T00:00:00"),
                updated_at=datetime.fromisoformat("2023-01-01T00:00:00"),
                last_sign_in_at=None,
                app_metadata={},
                user_metadata={},
                aud="test",
                role="authenticated",
                is_anonymous=False,
                confirmed_at=None,
            )

            result = await set_user_profile("user-123", profile, 3600)

            assert result is True
            mock_redis.set.assert_called_once()
            args, _ = mock_redis.set.call_args
            assert args[0] == "user:profile:user-123"
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
            profile_data: dict[str, Any] = {
                "id": "user-123",
                "email": "test@example.com",
                "email_confirmed_at": None,
                "phone": None,
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
                "last_sign_in_at": None,
                "app_metadata": {},
                "user_metadata": {},
                "aud": "test",
                "role": "authenticated",
                "is_anonymous": False,
                "confirmed_at": None,
            }
            mock_redis.get.return_value = json.dumps(profile_data)

            result = await get_user_profile("user-123")

            assert result is not None
            assert isinstance(result, UserProfileData)
            assert result.id == "user-123"
            assert result.email == "test@example.com"
            mock_redis.get.assert_called_once_with("user:profile:user-123")

    @pytest.mark.asyncio
    async def test_get_user_profile_none(self) -> None:
        """Test getting non-existent user profile."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.get.return_value = None

            result = await get_user_profile("user-123")

            assert result is None
            mock_redis.get.assert_called_once_with("user:profile:user-123")

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
            args, _ = mock_redis.set.call_args
            assert args[0] == "jwks:key:test-key"
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
            mock_redis.get.assert_called_once_with("jwks:key:test-key")

    @pytest.mark.asyncio
    async def test_get_jwks_key_none(self) -> None:
        """Test getting non-existent JWKS key."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.get.return_value = None

            result = await get_jwks_key("test-key")

            assert result is None
            mock_redis.get.assert_called_once_with("jwks:key:test-key")
