"""Async HTTP client base for the mcpwright suite.

Every suite server wraps ``httpx.AsyncClient`` with the same shape: a descriptive
User-Agent, optional fair-access throttling, and retry-with-exponential-backoff on
transient failures (429 / 5xx / network). That retry loop was copy-pasted four
times across edgar / census / soi; :class:`AsyncHttpClient` is the single copy.

Subclass it and add domain endpoint methods that call :meth:`request`,
:meth:`get_json`, :meth:`get_text`, or :meth:`download_to`. Pass ``error_cls`` to
raise your server's own error type (it should derive from
:class:`mcpwright_core.errors.HttpError`).
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

import httpx

from .errors import HttpError

if TYPE_CHECKING:
    from pathlib import Path

# A default chunk size for streamed downloads (1 MiB).
_CHUNK = 1 << 20


class RateLimiter:
    """Serialize requests so consecutive calls are spaced >= ``min_interval`` apart.

    For services with a fair-access policy (e.g. the SEC's ~10 req/s). Servers
    without such a limit simply don't pass one.
    """

    def __init__(self, min_interval: float) -> None:
        self._min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self) -> None:
        async with self._lock:
            delay = self._min_interval - (time.monotonic() - self._last)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last = time.monotonic()

    @classmethod
    def per_second(cls, rate: float) -> RateLimiter:
        """A limiter capped at ``rate`` requests per second."""
        return cls(1.0 / rate)


def _as_timeout(timeout: float | httpx.Timeout) -> httpx.Timeout:
    return timeout if isinstance(timeout, httpx.Timeout) else httpx.Timeout(timeout)


class AsyncHttpClient:
    """Thin async base over ``httpx.AsyncClient`` with retry/backoff + throttling.

    Construction mirrors what every suite client needs:

    - ``user_agent`` / ``headers`` — sent on every request (also settable as a
      class attribute ``USER_AGENT`` on a subclass).
    - ``timeout`` — seconds (or an ``httpx.Timeout``).
    - ``max_retries`` — attempts before giving up; backoff is ``2**attempt`` s.
    - ``rate_limiter`` — optional :class:`RateLimiter` awaited before each attempt.
    - ``error_cls`` — the exception type raised on unrecoverable failures.
    - ``follow_redirects`` — the client-wide default (override per call).
    """

    #: A subclass may set a default User-Agent here instead of passing one.
    USER_AGENT: str | None = None

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | httpx.Timeout = 30.0,
        max_retries: int = 3,
        rate_limiter: RateLimiter | None = None,
        error_cls: type[HttpError] = HttpError,
        follow_redirects: bool = True,
    ) -> None:
        hdrs: dict[str, str] = {"Accept-Encoding": "gzip, deflate"}
        ua = user_agent or self.USER_AGENT
        if ua:
            hdrs["User-Agent"] = ua
        if headers:
            hdrs.update(headers)
        self._client = httpx.AsyncClient(
            headers=hdrs,
            timeout=_as_timeout(timeout),
            follow_redirects=follow_redirects,
        )
        self._limiter = rate_limiter
        self._max_retries = max_retries
        self._error_cls = error_cls

    async def __aenter__(self) -> AsyncHttpClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        follow_redirects: bool | None = None,
    ) -> httpx.Response:
        """Issue a request with throttling and retry on transient failures.

        Returns the successful response. Raises ``error_cls`` on a 404, on a
        non-transient HTTP status, or after ``max_retries`` transient failures.
        A non-2xx that isn't 404/429/5xx is surfaced via ``raise_for_status``
        (4xx) or returned as-is for the caller to inspect (e.g. 3xx when
        ``follow_redirects`` is False).
        """
        last_exc: Exception | None = None
        redirects = (
            follow_redirects
            if follow_redirects is not None
            else httpx.USE_CLIENT_DEFAULT
        )
        for attempt in range(self._max_retries):
            if self._limiter is not None:
                await self._limiter.wait()
            try:
                resp = await self._client.request(
                    method, url, params=params, follow_redirects=redirects
                )
            except httpx.HTTPError as exc:  # network/timeout — retry
                last_exc = exc
                await asyncio.sleep(2**attempt)
                continue

            if resp.status_code == 404:
                raise self._error_cls(f"Not found: {resp.url}")
            if resp.status_code == 429 or resp.status_code >= 500:  # transient
                last_exc = self._error_cls(f"HTTP {resp.status_code} for {resp.url}")
                await asyncio.sleep(2**attempt)
                continue
            # 2xx and unfollowed 3xx are returned for the caller to use/inspect
            # (census reads a 3xx to detect a missing API key); other 4xx raise.
            if resp.is_client_error:
                resp.raise_for_status()
            return resp

        raise self._error_cls(
            f"Request failed after {self._max_retries} attempts: {url}"
        ) from last_exc

    async def get_json(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        """GET a URL and parse its JSON body."""
        return (await self.request("GET", url, params=params)).json()

    async def get_text(self, url: str, *, params: dict[str, Any] | None = None) -> str:
        """GET a URL and return its raw text body."""
        return (await self.request("GET", url, params=params)).text

    async def download_to(
        self, url: str, dest: Path, *, chunk_size: int = _CHUNK
    ) -> int:
        """Stream a (potentially large) URL to ``dest``; return bytes written.

        Streams to disk rather than buffering in memory, and retries transient
        errors (429 / 5xx / network) with exponential backoff. Creates parent
        directories as needed. Raises ``error_cls`` on a missing file or after
        ``max_retries`` failures.
        """
        dest.parent.mkdir(parents=True, exist_ok=True)
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                written = 0
                async with self._client.stream("GET", url) as resp:
                    if resp.status_code == 404:
                        raise self._error_cls(f"Not found: {url}")
                    if resp.status_code == 429 or resp.status_code >= 500:
                        last_exc = self._error_cls(f"HTTP {resp.status_code} for {url}")
                        await asyncio.sleep(2**attempt)
                        continue
                    resp.raise_for_status()
                    with dest.open("wb") as fh:
                        async for chunk in resp.aiter_bytes(chunk_size=chunk_size):
                            fh.write(chunk)
                            written += len(chunk)
                return written
            except httpx.HTTPError as exc:  # network/timeout — retry
                last_exc = exc
                await asyncio.sleep(2**attempt)
                continue

        raise self._error_cls(
            f"Download failed after {self._max_retries} attempts: {url}"
        ) from last_exc
