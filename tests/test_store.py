from pathlib import Path

import pytest

from mcpwright_core.store import BaseStore


class WidgetStore(BaseStore):
    APP_DIR = "mcpwright-test"
    DB_NAME = "widgets.sqlite3"
    STORE_ENV_VAR = "WIDGET_STORE"
    DATA_TABLE = "widget"

    def replace_all(self, records: list[dict[str, object]], vintage: int) -> int:
        conn = self.connect()
        with conn:  # one transaction
            conn.execute("DROP TABLE IF EXISTS widget")
            conn.execute("CREATE TABLE widget (id TEXT PRIMARY KEY, name TEXT)")
            conn.executemany(
                "INSERT OR REPLACE INTO widget (id, name) VALUES (?, ?)",
                [(r["id"], r["name"]) for r in records],
            )
            self._write_meta(conn, {"vintage": vintage, "row_count": len(records)})
        return len(records)

    def get(self, widget_id: str) -> dict[str, object] | None:
        conn = self.connect()
        if not self._table_exists("widget"):
            return None
        row = conn.execute("SELECT * FROM widget WHERE id = ?", (widget_id,)).fetchone()
        return self._row_dict(row) if row is not None else None


@pytest.fixture
def store(tmp_path: Path) -> WidgetStore:
    return WidgetStore(tmp_path / "widgets.sqlite3")


def test_default_path_uses_class_attrs(monkeypatch) -> None:
    monkeypatch.delenv("WIDGET_STORE", raising=False)
    p = WidgetStore.default_path()
    assert p.name == "widgets.sqlite3"
    assert p.parent.name == "mcpwright-test"


def test_default_path_env_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WIDGET_STORE", str(tmp_path / "x.sqlite3"))
    assert WidgetStore.default_path() == tmp_path / "x.sqlite3"


def test_not_loaded_before_write(store: WidgetStore) -> None:
    assert store.is_loaded() is False
    assert store.metadata() == {}
    assert store._int_meta("vintage") is None
    assert store.get("a") is None


def test_loaded_after_write(store: WidgetStore) -> None:
    n = store.replace_all(
        [{"id": "a", "name": "Alpha"}, {"id": "b", "name": "Beta"}], 2024
    )
    assert n == 2
    assert store.is_loaded() is True
    assert store._int_meta("vintage") == 2024
    assert store._int_meta("row_count") == 2
    assert store.metadata()["vintage"] == "2024"
    assert store.get("a") == {"id": "a", "name": "Alpha"}
    assert store.get("missing") is None


def test_replace_all_is_atomic_rebuild(store: WidgetStore) -> None:
    store.replace_all([{"id": "a", "name": "Alpha"}], 2023)
    store.replace_all([{"id": "b", "name": "Beta"}], 2024)
    assert store.get("a") is None  # old data dropped
    assert store.get("b") == {"id": "b", "name": "Beta"}
    assert store._int_meta("vintage") == 2024


def test_connect_is_idempotent_and_closes(store: WidgetStore) -> None:
    c1 = store.connect()
    c2 = store.connect()
    assert c1 is c2
    store.close()
    assert store._conn is None
    assert store.connect() is not c1  # a fresh connection after close
