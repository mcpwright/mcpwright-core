import pytest

from mcpwright_core.cache import TTLCache


@pytest.mark.asyncio
async def test_cache_hit_and_miss() -> None:
    c = TTLCache()
    assert await c.get("k") == (False, None)
    await c.set("k", 123, ttl=60, size=8)
    assert await c.get("k") == (True, 123)


@pytest.mark.asyncio
async def test_cache_expiry() -> None:
    c = TTLCache()
    await c.set("k", "v", ttl=-1, size=1)  # already expired
    hit, _ = await c.get("k")
    assert hit is False


@pytest.mark.asyncio
async def test_cache_byte_budget_eviction() -> None:
    c = TTLCache(max_bytes=100)
    await c.set("a", "x", ttl=60, size=60)
    await c.set("b", "y", ttl=60, size=60)  # 120 > 100 -> evict oldest ("a")
    assert (await c.get("a"))[0] is False
    assert (await c.get("b"))[0] is True


@pytest.mark.asyncio
async def test_cache_overwrite_adjusts_bytes() -> None:
    c = TTLCache(max_bytes=100)
    await c.set("a", "x", ttl=60, size=40)
    await c.set("a", "y", ttl=60, size=40)  # overwrite, not double-counted
    await c.set("b", "z", ttl=60, size=40)  # 80 total -> both fit
    assert (await c.get("a")) == (True, "y")
    assert (await c.get("b")) == (True, "z")
