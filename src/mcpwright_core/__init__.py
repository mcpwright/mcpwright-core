"""mcpwright-core — the shared runtime toolkit for the mcpwright suite.

Composable pieces, not a monolith: import what your server needs.

- :class:`AsyncHttpClient` / :class:`RateLimiter` — the retry/backoff HTTP base.
- :class:`TTLCache` — in-memory TTL + byte-budget cache (for live-call servers).
- :data:`READ_ONLY` / :func:`app_context` — server-side tool helpers.
- :class:`McpwrightError` / :class:`HttpError` — the error hierarchy.
"""

from __future__ import annotations

from .cache import TTLCache
from .errors import HttpError, McpwrightError
from .http import AsyncHttpClient, RateLimiter
from .server import READ_ONLY, app_context

__all__ = [
    "READ_ONLY",
    "AsyncHttpClient",
    "HttpError",
    "McpwrightError",
    "RateLimiter",
    "TTLCache",
    "app_context",
]

__version__ = "0.1.1"
