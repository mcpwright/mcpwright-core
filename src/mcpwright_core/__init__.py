"""mcpwright-core — the shared runtime toolkit for the mcpwright suite.

Composable pieces, not a monolith: import what your server needs.

- :class:`AsyncHttpClient` / :class:`RateLimiter` — the retry/backoff HTTP base.
- :class:`TTLCache` — in-memory TTL + byte-budget cache (for live-call servers).
- :class:`BaseStore` / :func:`cache_path` — SQLite local-store base + path resolution.
- :data:`READ_ONLY` / :func:`app_context` / :func:`ensure_loaded` / :func:`run_cli` — server helpers.
- :class:`McpwrightError` / :class:`HttpError` — the error hierarchy.
"""

from __future__ import annotations

from .cache import TTLCache
from .errors import HttpError, McpwrightError
from .http import AsyncHttpClient, RateLimiter
from .paths import cache_dir, cache_path
from .server import READ_ONLY, app_context, ensure_loaded, run_cli
from .store import BaseStore

__all__ = [
    "READ_ONLY",
    "AsyncHttpClient",
    "BaseStore",
    "HttpError",
    "McpwrightError",
    "RateLimiter",
    "TTLCache",
    "app_context",
    "cache_dir",
    "cache_path",
    "ensure_loaded",
    "run_cli",
]

__version__ = "0.1.2"
