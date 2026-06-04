from pathlib import Path

from mcpwright_core.paths import cache_path


def test_env_override_wins(monkeypatch) -> None:
    monkeypatch.setenv("MY_STORE", "/tmp/custom/db.sqlite3")
    assert cache_path("myapp", "db.sqlite3", "MY_STORE") == Path(
        "/tmp/custom/db.sqlite3"
    )


def test_default_path_under_cache_dir(monkeypatch) -> None:
    monkeypatch.delenv("MY_STORE", raising=False)
    p = cache_path("myapp", "db.sqlite3", "MY_STORE")
    assert p.name == "db.sqlite3"
    assert p.parent.name == "myapp"
