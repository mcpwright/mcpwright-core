import httpx
import pytest
import respx

from mcpwright_core.errors import HttpError
from mcpwright_core.http import AsyncHttpClient, RateLimiter

URL = "https://example.test/data.json"


class _MyError(HttpError):
    pass


@respx.mock
@pytest.mark.asyncio
async def test_get_json_ok() -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    async with AsyncHttpClient(user_agent="t") as client:
        data = await client.get_json(URL)
    assert data == {"ok": True}


@respx.mock
@pytest.mark.asyncio
async def test_get_text_ok() -> None:
    respx.get(URL).mock(return_value=httpx.Response(200, text="hello"))
    async with AsyncHttpClient() as client:
        assert await client.get_text(URL) == "hello"


@respx.mock
@pytest.mark.asyncio
async def test_404_raises_error_cls() -> None:
    respx.get(URL).mock(return_value=httpx.Response(404))
    async with AsyncHttpClient(error_cls=_MyError) as client:
        with pytest.raises(_MyError):
            await client.get_json(URL)


@respx.mock
@pytest.mark.asyncio
async def test_retries_then_succeeds_on_500() -> None:
    route = respx.get(URL).mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json={"ok": 1}),
        ]
    )
    async with AsyncHttpClient(max_retries=3) as client:
        data = await client.get_json(URL)
    assert data == {"ok": 1}
    assert route.call_count == 2  # one transient, one success


@respx.mock
@pytest.mark.asyncio
async def test_gives_up_after_max_retries() -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(500))
    async with AsyncHttpClient(max_retries=2) as client:
        with pytest.raises(HttpError):
            await client.get_json(URL)
    assert route.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_network_error_retried() -> None:
    route = respx.get(URL).mock(
        side_effect=[httpx.ConnectError("boom"), httpx.Response(200, json={"n": 1})]
    )
    async with AsyncHttpClient(max_retries=3) as client:
        assert await client.get_json(URL) == {"n": 1}
    assert route.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_no_follow_redirects_returns_3xx() -> None:
    # With redirects off, a 3xx isn't an error: the caller gets the response to
    # inspect (this is how census detects a missing API key).
    respx.get(URL).mock(return_value=httpx.Response(302, headers={"location": "/x"}))
    async with AsyncHttpClient() as client:
        resp = await client.request("GET", URL, follow_redirects=False)
    assert resp.status_code == 302


@respx.mock
@pytest.mark.asyncio
async def test_download_to(tmp_path) -> None:
    body = b"x" * 5000
    respx.get(URL).mock(return_value=httpx.Response(200, content=body))
    dest = tmp_path / "sub" / "out.bin"
    async with AsyncHttpClient() as client:
        written = await client.download_to(URL, dest, chunk_size=1024)
    assert written == len(body)
    assert dest.read_bytes() == body


@respx.mock
@pytest.mark.asyncio
async def test_download_to_404_raises(tmp_path) -> None:
    respx.get(URL).mock(return_value=httpx.Response(404))
    async with AsyncHttpClient(error_cls=_MyError) as client:
        with pytest.raises(_MyError):
            await client.download_to(URL, tmp_path / "out.bin")


@pytest.mark.asyncio
async def test_rate_limiter_spaces_calls() -> None:
    import time

    limiter = RateLimiter.per_second(50)  # 20ms apart
    start = time.monotonic()
    await limiter.wait()
    await limiter.wait()
    await limiter.wait()
    assert time.monotonic() - start >= 0.04  # two enforced gaps of ~20ms
