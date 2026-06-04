"""A SQLite-backed local-store base for bulk-download-once suite servers.

census and soi both download a static dataset once into a local SQLite file and
serve every lookup offline. The machinery around that — connection lifecycle, a
small key/value ``meta`` table, "is the data loaded?", and metadata reads/writes
— is identical between them; only the schema and the domain queries differ.
:class:`BaseStore` is that shared machinery. Subclass it, set the four class
attributes, and add your schema-specific ``replace_*`` writers and query methods.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from .paths import cache_path

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


class BaseStore:
    """Shared SQLite store plumbing: connection, ``meta`` table, load-state.

    Subclasses set:

    - ``APP_DIR`` — the per-server cache subdirectory (e.g. ``"mcpwright-soi"``).
    - ``DB_NAME`` — the SQLite filename (e.g. ``"soi.sqlite3"``).
    - ``STORE_ENV_VAR`` — env var to override the store path.
    - ``DATA_TABLE`` — the table whose presence + non-emptiness means "loaded".
      Must be a trusted identifier literal: it is interpolated into SQL in
      :meth:`is_loaded`, not bound, so never wire it to runtime/config input.

    and add their own ``replace_*`` writers (which should call
    :meth:`_write_meta` inside their transaction) and query methods (which can
    use :meth:`_row_dict`).
    """

    APP_DIR: str
    DB_NAME: str
    STORE_ENV_VAR: str
    DATA_TABLE: str

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or self.default_path()
        self._conn: sqlite3.Connection | None = None

    @classmethod
    def default_path(cls) -> Path:
        """Where this store's SQLite file lives (override via ``STORE_ENV_VAR``)."""
        return cache_path(cls.APP_DIR, cls.DB_NAME, cls.STORE_ENV_VAR)

    # --- connection lifecycle ----------------------------------------------
    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            self._conn = conn
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # --- state -------------------------------------------------------------
    def is_loaded(self) -> bool:
        """True once ``DATA_TABLE`` exists and holds at least one row."""
        if not self._table_exists(self.DATA_TABLE):
            return False
        conn = self.connect()
        count = conn.execute(f"SELECT COUNT(*) FROM {self.DATA_TABLE}").fetchone()[0]
        return bool(count)

    def metadata(self) -> dict[str, str]:
        """All key/value pairs from the ``meta`` table (empty if none)."""
        conn = self.connect()
        if not self._table_exists("meta"):
            return {}
        return {
            str(r["key"]): str(r["value"])
            for r in conn.execute("SELECT key, value FROM meta")
        }

    # --- internals (inherited by subclasses) -------------------------------
    def _table_exists(self, name: str) -> bool:
        conn = self.connect()
        return (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()
            is not None
        )

    def _meta(self, key: str) -> str | None:
        conn = self.connect()
        if not self._table_exists("meta"):
            return None
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row is not None else None

    def _int_meta(self, key: str) -> int | None:
        v = self._meta(key)
        return int(v) if v is not None else None

    @staticmethod
    def _write_meta(conn: sqlite3.Connection, values: Mapping[str, object]) -> None:
        """Create the ``meta`` table if needed and upsert ``values``.

        Call inside the writer's ``with conn`` transaction so the metadata lands
        atomically with the data.
        """
        conn.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        conn.executemany(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            [(k, str(v)) for k, v in values.items()],
        )

    @staticmethod
    def _row_dict(row: sqlite3.Row) -> dict[str, object]:
        """A plain column->value dict for a ``sqlite3.Row``."""
        # sqlite3.Row iterates VALUES, not column names — .keys() is required.
        return {key: row[key] for key in row.keys()}  # noqa: SIM118
