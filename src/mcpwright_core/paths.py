"""Per-user cache-directory resolution for store-backed suite servers.

census and soi both download a dataset once into a local SQLite file under the
OS cache directory; this is the single copy of "where does that file live",
including the platform rules and the per-server environment override.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def cache_dir() -> Path:
    """The per-user cache directory for this platform.

    macOS → ``~/Library/Caches``; Windows → ``%LOCALAPPDATA%``; otherwise the
    XDG base dir (``$XDG_CACHE_HOME`` or ``~/.cache``).
    """
    # Bind to a local so mypy doesn't prune the other branches as unreachable
    # (it narrows direct `sys.platform` comparisons to the checking platform).
    platform = sys.platform
    if platform == "darwin":
        return Path.home() / "Library" / "Caches"
    if platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA")
        return Path(base) if base else Path.home() / "AppData" / "Local"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")


def cache_path(app_dir: str, db_name: str, env_var: str) -> Path:
    """Where a server's local store lives (override with ``$env_var``).

    ``app_dir`` is the per-server subdirectory (e.g. ``"mcpwright-soi"``),
    ``db_name`` the SQLite filename (e.g. ``"soi.sqlite3"``), and ``env_var`` an
    absolute-path override (e.g. ``"SOI_MCP_STORE"``).
    """
    override = os.environ.get(env_var)
    if override:
        return Path(override)
    return cache_dir() / app_dir / db_name
