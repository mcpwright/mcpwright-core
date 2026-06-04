"""Error hierarchy shared across the mcpwright suite.

Every suite server raises a domain-specific error (``EdgarError``, ``CensusError``,
``SoiError``, …); they all ultimately derive from :class:`McpwrightError` so callers
can catch the whole family with one ``except`` if they want to. The HTTP client
raises :class:`HttpError` (or a subclass a server passes via ``error_cls``).
"""

from __future__ import annotations


class McpwrightError(RuntimeError):
    """Base class for every recoverable error raised by the mcpwright suite."""


class HttpError(McpwrightError):
    """An HTTP request failed in a way we can't recover from (after retries)."""
