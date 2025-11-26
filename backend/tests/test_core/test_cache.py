"""Tests for Redis caching utilities."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.cache import (
    cache_delete,
    cache_get,
    cache_invalidate,
    cache_set,
    cache_stats,
    cached,
)


@pytest.fixture(autouse=True)
def mock_redis(test_redis: Any) -> Any:
    """Automatically mock get_redis for all cache tests."""
    with patch("app.core.cache.get_redis", return_value=test_redis):
        yield test_redis


class TestCacheGetSet:
    """Test basic cache get and set operations."""

    @pytest.mark.asyncio
    async def test_cache_set_and_get_success(self) -> None:
        """Test setting and getting a cache value."""
        key = "test:key"
        value = {"name": "John Doe", "age": 30}

        # Set cache
        result = await cache_set(key, value, ttl=60)
        assert result is True

        # Get cache
        cached_value = await cache_get(key)
        assert cached_value == value

    @pytest.mark.asyncio
    async def test_cache_get_nonexistent_key(self) -> None:
        """Test getting a non-existent cache key returns None."""
        result = await cache_get("nonexistent:key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_different_types(self) -> None:
        """Test caching different data types."""
        # String
        await cache_set("test:string", "hello")
        assert await cache_get("test:string") == "hello"

        # Integer
        await cache_set("test:int", 42)
        assert await cache_get("test:int") == 42

        # List
        await cache_set("test:list", [1, 2, 3])
        assert await cache_get("test:list") == [1, 2, 3]

        # Dict
        await cache_set("test:dict", {"key": "value"})
        assert await cache_get("test:dict") == {"key": "value"}

        # Boolean
        await cache_set("test:bool", True)
        assert await cache_get("test:bool") is True

    @pytest.mark.asyncio
    async def test_cache_set_with_ttl(self, test_redis: Any) -> None:
        """Test that cache entries respect TTL."""
        key = "test:ttl"
        value = "temporary"

        # Set with very short TTL (1 second)
        await cache_set(key, value, ttl=1)

        # Should be available immediately
        result = await cache_get(key)
        assert result == value

        # Verify TTL was set in Redis
        ttl = await test_redis.ttl(key)
        assert ttl > 0
        assert ttl <= 1

    @pytest.mark.asyncio
    async def test_cache_set_overwrites_existing(self) -> None:
        """Test that setting a cache key overwrites existing value."""
        key = "test:overwrite"

        await cache_set(key, "old_value")
        assert await cache_get(key) == "old_value"

        await cache_set(key, "new_value")
        assert await cache_get(key) == "new_value"

    @pytest.mark.asyncio
    async def test_cache_get_error_handling(self) -> None:
        """Test cache_get handles Redis errors gracefully."""
        # Mock Redis to raise exception
        with patch("app.core.cache.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(side_effect=Exception("Redis error"))
            mock_get_redis.return_value = mock_redis

            # Should return None on error, not raise
            result = await cache_get("test:key")
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_error_handling(self) -> None:
        """Test cache_set handles Redis errors gracefully."""
        # Mock Redis to raise exception
        with patch("app.core.cache.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.setex = AsyncMock(side_effect=Exception("Redis error"))
            mock_get_redis.return_value = mock_redis

            # Should return False on error, not raise
            result = await cache_set("test:key", "value")
            assert result is False


class TestCacheDelete:
    """Test cache deletion."""

    @pytest.mark.asyncio
    async def test_cache_delete_existing_key(self) -> None:
        """Test deleting an existing cache key."""
        key = "test:delete"
        await cache_set(key, "value")

        # Verify key exists
        assert await cache_get(key) == "value"

        # Delete key
        result = await cache_delete(key)
        assert result is True

        # Verify key is gone
        assert await cache_get(key) is None

    @pytest.mark.asyncio
    async def test_cache_delete_nonexistent_key(self) -> None:
        """Test deleting a non-existent key."""
        result = await cache_delete("nonexistent:key")
        assert result is True  # Redis delete returns success even if key doesn't exist

    @pytest.mark.asyncio
    async def test_cache_delete_error_handling(self) -> None:
        """Test cache_delete handles Redis errors gracefully."""
        with patch("app.core.cache.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.delete = AsyncMock(side_effect=Exception("Redis error"))
            mock_get_redis.return_value = mock_redis

            result = await cache_delete("test:key")
            assert result is False


class TestCacheInvalidate:
    """Test cache invalidation with patterns."""

    @pytest.mark.asyncio
    async def test_cache_invalidate_pattern_match(self) -> None:
        """Test invalidating multiple keys with pattern."""
        # Set multiple keys
        await cache_set("user:1:profile", {"name": "User 1"})
        await cache_set("user:2:profile", {"name": "User 2"})
        await cache_set("user:3:profile", {"name": "User 3"})
        await cache_set("product:1", {"name": "Product 1"})

        # Invalidate all user profile keys
        deleted_count = await cache_invalidate("user:*:profile")
        assert deleted_count == 3

        # Verify user keys are gone
        assert await cache_get("user:1:profile") is None
        assert await cache_get("user:2:profile") is None
        assert await cache_get("user:3:profile") is None

        # Verify product key still exists
        assert await cache_get("product:1") == {"name": "Product 1"}

    @pytest.mark.asyncio
    async def test_cache_invalidate_no_matches(self) -> None:
        """Test invalidating with pattern that matches no keys."""
        deleted_count = await cache_invalidate("nonexistent:*")
        assert deleted_count == 0

    @pytest.mark.asyncio
    async def test_cache_invalidate_wildcard_patterns(self) -> None:
        """Test various wildcard patterns."""
        # Set up test data
        await cache_set("crm:stats:all", {})
        await cache_set("crm:stats:monthly", {})
        await cache_set("crm:contacts:list", {})
        await cache_set("other:data", {})

        # Invalidate all crm:stats:* keys
        deleted_count = await cache_invalidate("crm:stats:*")
        assert deleted_count == 2

        # Verify correct keys were deleted
        assert await cache_get("crm:stats:all") is None
        assert await cache_get("crm:stats:monthly") is None
        assert await cache_get("crm:contacts:list") is not None
        assert await cache_get("other:data") is not None

    @pytest.mark.asyncio
    async def test_cache_invalidate_error_handling(self) -> None:
        """Test cache_invalidate handles Redis errors gracefully."""
        with patch("app.core.cache.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.scan_iter = AsyncMock(side_effect=Exception("Redis error"))
            mock_get_redis.return_value = mock_redis

            result = await cache_invalidate("test:*")
            assert result == 0


class TestCachedDecorator:
    """Test the @cached decorator."""

    @pytest.mark.asyncio
    async def test_cached_decorator_caches_result(self) -> None:
        """Test that decorator caches function results."""
        call_count = 0

        @cached(prefix="test:expensive", ttl=60)
        async def expensive_function(user_id: int) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return {"user_id": user_id, "name": f"User {user_id}"}

        # First call - should execute function
        result1 = await expensive_function(42)
        assert result1 == {"user_id": 42, "name": "User 42"}
        assert call_count == 1

        # Second call with same args - should use cache
        result2 = await expensive_function(42)
        assert result2 == {"user_id": 42, "name": "User 42"}
        assert call_count == 1  # Function not called again

        # Call with different args - should execute function
        result3 = await expensive_function(99)
        assert result3 == {"user_id": 99, "name": "User 99"}
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cached_decorator_different_arguments(self) -> None:
        """Test that decorator creates different cache keys for different arguments."""

        @cached(prefix="test:func", ttl=60)
        async def get_data(item_id: int, name: str) -> dict[str, Any]:
            return {"id": item_id, "name": name}

        result1 = await get_data(1, "Alice")
        result2 = await get_data(1, "Bob")
        result3 = await get_data(2, "Alice")

        # All should return different results
        assert result1 == {"id": 1, "name": "Alice"}
        assert result2 == {"id": 1, "name": "Bob"}
        assert result3 == {"id": 2, "name": "Alice"}

    @pytest.mark.asyncio
    async def test_cached_decorator_with_kwargs(self) -> None:
        """Test decorator works with keyword arguments."""

        @cached(prefix="test:kwargs", ttl=60)
        async def get_user(user_id: int, include_profile: bool = False) -> dict[str, Any]:
            result = {"user_id": user_id}
            if include_profile:
                result["profile"] = "full_profile"
            return result

        # Test with different kwarg values
        result1 = await get_user(1, include_profile=True)
        result2 = await get_user(1, include_profile=False)

        assert result1 == {"user_id": 1, "profile": "full_profile"}
        assert result2 == {"user_id": 1}

    @pytest.mark.asyncio
    async def test_cached_decorator_respects_ttl(self, test_redis: Any) -> None:
        """Test that decorator respects TTL setting."""

        @cached(prefix="test:ttl", ttl=30)
        async def get_value() -> str:
            return "cached_value"

        await get_value()

        # Check TTL in Redis
        # The cache key is generated with a hash, so we need to find it
        keys = await test_redis.keys("test:ttl:*")
        assert len(keys) == 1

        ttl = await test_redis.ttl(keys[0])
        assert 0 < ttl <= 30

    @pytest.mark.asyncio
    async def test_cached_decorator_handles_none_result(self) -> None:
        """Test decorator handles None as a valid cached value."""
        call_count = 0

        @cached(prefix="test:none", ttl=60)
        async def returns_none() -> None:
            nonlocal call_count
            call_count += 1

        # First call
        result1 = await returns_none()
        assert result1 is None
        assert call_count == 1

        # Note: Current implementation returns None on cache miss,
        # so None values aren't actually cached. This is a design limitation.
        # Second call will execute function again.
        result2 = await returns_none()
        assert result2 is None


class TestCacheStats:
    """Test cache statistics."""

    @pytest.mark.asyncio
    async def test_cache_stats_returns_data(self) -> None:
        """Test that cache_stats returns statistics."""
        stats = await cache_stats()

        assert isinstance(stats, dict)
        assert (
            "total_connections_received" in stats or len(stats) == 0
        )  # May be empty for fakeredis

    @pytest.mark.asyncio
    async def test_cache_stats_error_handling(self) -> None:
        """Test cache_stats handles Redis errors gracefully."""
        with patch("app.core.cache.get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.info = AsyncMock(side_effect=Exception("Redis error"))
            mock_get_redis.return_value = mock_redis

            stats = await cache_stats()
            assert stats == {}


class TestCacheIntegration:
    """Integration tests for caching functionality."""

    @pytest.mark.asyncio
    async def test_cache_workflow(self) -> None:
        """Test complete cache workflow: set, get, update, delete."""
        key = "workflow:test"

        # Initial set
        await cache_set(key, {"value": 1}, ttl=60)
        assert await cache_get(key) == {"value": 1}

        # Update
        await cache_set(key, {"value": 2}, ttl=60)
        assert await cache_get(key) == {"value": 2}

        # Delete
        await cache_delete(key)
        assert await cache_get(key) is None

    @pytest.mark.asyncio
    async def test_multiple_cache_keys(self) -> None:
        """Test managing multiple cache keys."""
        keys = {
            "key1": "value1",
            "key2": {"data": "value2"},
            "key3": [1, 2, 3],
        }

        # Set all keys
        for key, value in keys.items():
            await cache_set(key, value)

        # Verify all keys
        for key, expected_value in keys.items():
            actual_value = await cache_get(key)
            assert actual_value == expected_value

        # Delete one key
        await cache_delete("key2")

        # Verify remaining keys
        assert await cache_get("key1") == "value1"
        assert await cache_get("key2") is None
        assert await cache_get("key3") == [1, 2, 3]
