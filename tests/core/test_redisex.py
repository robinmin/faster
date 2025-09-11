import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

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
            mock_redis.hget.return_value = '["admin", "moderator"]'

            result = await sysmap_get(str(MapCategory.TAG_ROLE), "tag-important")

            assert result == {"tag-important": '["admin", "moderator"]'}
            mock_redis.hget.assert_called_once_with("sys:map:tag_role", "tag-important")

    @pytest.mark.asyncio
    async def test_sysmap_get_tag_roles_not_found(self) -> None:
        """Test getting tag roles when tag doesn't exist."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.hget.return_value = None

            result = await sysmap_get(str(MapCategory.TAG_ROLE), "tag-nonexistent")

            assert result == {}
            mock_redis.hget.assert_called_once_with("sys:map:tag_role", "tag-nonexistent")

    @pytest.mark.asyncio
    async def test_sysmap_set_tag_roles(self) -> None:
        """Test setting tag roles using sysmap_set."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            mapping = {
                "tag-important": '["admin", "moderator"]',
                "tag-public": '["user"]',
            }
            result = await sysmap_set(str(MapCategory.TAG_ROLE), mapping)

            assert result is True
            # Verify the mapping was converted to JSON strings
            expected_mapping = {
                "tag-important": '["admin", "moderator"]',
                "tag-public": '["user"]',
            }
            mock_redis.hset.assert_called_once_with("sys:map:tag_role", expected_mapping)

    @pytest.mark.asyncio
    async def test_sysmap_get_single_string_value(self) -> None:
        """Test getting a single string value (non-JSON) using sysmap_get."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.hget.return_value = "admin"

            result = await sysmap_get(str(MapCategory.TAG_ROLE), "tag-simple")

            assert result == {"tag-simple": "admin"}
            mock_redis.hget.assert_called_once_with("sys:map:tag_role", "tag-simple")

    @pytest.mark.asyncio
    async def test_sysmap_get_invalid_json(self) -> None:
        """Test getting invalid JSON value using sysmap_get."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.hget.return_value = '["invalid json'

            result = await sysmap_get(str(MapCategory.TAG_ROLE), "tag-broken")

            assert result == {"tag-broken": '["invalid json'}
            mock_redis.hget.assert_called_once_with("sys:map:tag_role", "tag-broken")

    @pytest.mark.asyncio
    async def test_sysmap_set_mixed_value_types(self) -> None:
        """Test setting mixed value types using sysmap_set."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            mapping = {"tag-list": '["admin", "user"]', "tag-string": "single-value"}
            result = await sysmap_set(str(MapCategory.TAG_ROLE), mapping)

            assert result is True
            # Verify only lists were converted to JSON
            expected_mapping = {"tag-list": '["admin", "user"]', "tag-string": "single-value"}
            mock_redis.hset.assert_called_once_with("sys:map:tag_role", expected_mapping)

    @pytest.mark.asyncio
    async def test_sysmap_get_all_values(self) -> None:
        """Test getting all values in a category using sysmap_get with left=None."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.hgetall.return_value = {
                "tag-admin": '["admin", "superuser"]',
                "tag-user": '["user"]',
                "tag-simple": "basic",
            }

            result = await sysmap_get(str(MapCategory.TAG_ROLE))

            assert result == {
                "tag-admin": '["admin", "superuser"]',
                "tag-user": '["user"]',
                "tag-simple": "basic",
            }
            mock_redis.hgetall.assert_called_once_with("sys:map:tag_role")

    @pytest.mark.asyncio
    async def test_sysmap_get_all_values_empty(self) -> None:
        """Test getting all values when category is empty."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.hgetall.return_value = {}

            result = await sysmap_get(str(MapCategory.TAG_ROLE))

            assert result == {}
            mock_redis.hgetall.assert_called_once_with("sys:map:tag_role")

    @pytest.mark.asyncio
    async def test_sysmap_get_all_values_with_mixed_types(self) -> None:
        """Test getting all values with mixed JSON and string types."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.hgetall.return_value = {
                "tag-json": '{"role": "admin", "permissions": ["read", "write"]}',
                "tag-list": '["admin", "user"]',
                "tag-string": "simple-value",
                "tag-invalid": '["broken json',
            }

            result = await sysmap_get(str(MapCategory.TAG_ROLE))

            assert result == {
                "tag-json": '{"role": "admin", "permissions": ["read", "write"]}',
                "tag-list": '["admin", "user"]',
                "tag-string": "simple-value",
                "tag-invalid": '["broken json',
            }
            mock_redis.hgetall.assert_called_once_with("sys:map:tag_role")


class TestAuthModuleFunctions:
    """Test auth module utility functions."""

    @pytest.mark.asyncio
    async def test_set_user_profile(self) -> None:
        """Test setting user profile."""
        with patch("faster.core.redisex.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_redis.set.return_value = True

            # Create a mock user profile JSON string
            profile_data: dict[str, Any] = {
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
            profile_json = json.dumps(profile_data)

            result = await set_user_profile("user-123", profile_json, 3600)

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
            assert isinstance(result, str)
            # Parse the JSON to verify the content
            parsed_result = json.loads(result)
            assert parsed_result["id"] == "user-123"
            assert parsed_result["email"] == "test@example.com"
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
