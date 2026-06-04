import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from mcpwright_core.server import READ_ONLY, app_context, ensure_loaded, run_cli


def test_read_only_annotation() -> None:
    assert READ_ONLY.readOnlyHint is True
    assert READ_ONLY.openWorldHint is True


@dataclass
class _AppCtx:
    value: int


def test_app_context_casts_lifespan_context() -> None:
    # Mimic the MCP Context shape: ctx.request_context.lifespan_context
    app = _AppCtx(value=42)
    ctx = SimpleNamespace(request_context=SimpleNamespace(lifespan_context=app))
    got = app_context(ctx, _AppCtx)  # type: ignore[arg-type]
    assert got is app
    assert got.value == 42


# --- ensure_loaded ---------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_loaded_loads_when_empty() -> None:
    state = {"loaded": False, "loads": 0}

    async def load() -> None:
        state["loads"] += 1
        state["loaded"] = True

    v = await ensure_loaded(
        asyncio.Lock(),
        is_loaded=lambda: state["loaded"],
        load=load,
        version=lambda: 2022,
    )
    assert v == 2022
    assert state["loads"] == 1


@pytest.mark.asyncio
async def test_ensure_loaded_skips_when_already_loaded() -> None:
    state = {"loads": 0}

    async def load() -> None:
        state["loads"] += 1

    await ensure_loaded(
        asyncio.Lock(), is_loaded=lambda: True, load=load, version=lambda: 1
    )
    assert state["loads"] == 0


@pytest.mark.asyncio
async def test_ensure_loaded_concurrent_loads_once() -> None:
    state = {"loaded": False, "loads": 0}
    lock = asyncio.Lock()

    async def load() -> None:
        state["loads"] += 1
        await asyncio.sleep(0.01)
        state["loaded"] = True

    await asyncio.gather(
        *(
            ensure_loaded(
                lock,
                is_loaded=lambda: state["loaded"],
                load=load,
                version=lambda: 7,
            )
            for _ in range(5)
        )
    )
    assert state["loads"] == 1  # only the first acquirer loads


# --- run_cli ---------------------------------------------------------------


class _FakeError(Exception):
    pass


def _spy_loader(record: list):
    async def loader(year):
        record.append(year)

    return loader


def test_run_cli_no_args_runs_server(monkeypatch) -> None:
    ran = []
    mcp = SimpleNamespace(run=lambda: ran.append(True))
    monkeypatch.setattr("sys.argv", ["mcpwright-x"])
    run_cli(mcp, loader=_spy_loader([]), error=_FakeError)
    assert ran == [True]


def test_run_cli_setup_calls_loader(monkeypatch) -> None:
    record: list = []
    mcp = SimpleNamespace(run=lambda: record.append("RAN_SERVER"))
    monkeypatch.setattr("sys.argv", ["mcpwright-x", "setup"])
    run_cli(mcp, loader=_spy_loader(record), error=_FakeError)
    assert record == [None]  # loader called with year=None, server not run


def test_run_cli_refresh_with_year(monkeypatch) -> None:
    record: list = []
    mcp = SimpleNamespace(run=lambda: None)
    monkeypatch.setattr("sys.argv", ["mcpwright-x", "refresh", "2021"])
    run_cli(mcp, loader=_spy_loader(record), error=_FakeError, accepts_year=True)
    assert record == [2021]


def test_run_cli_year_ignored_when_not_accepted(monkeypatch) -> None:
    record: list = []
    mcp = SimpleNamespace(run=lambda: None)
    monkeypatch.setattr("sys.argv", ["mcpwright-x", "refresh", "2021"])
    run_cli(mcp, loader=_spy_loader(record), error=_FakeError, accepts_year=False)
    assert record == [None]  # year arg not parsed


def test_run_cli_bad_year_exits(monkeypatch) -> None:
    mcp = SimpleNamespace(run=lambda: None)
    monkeypatch.setattr("sys.argv", ["mcpwright-x", "refresh", "nope"])
    with pytest.raises(SystemExit) as exc:
        run_cli(mcp, loader=_spy_loader([]), error=_FakeError, accepts_year=True)
    assert exc.value.code == 1


def test_run_cli_domain_error_exits(monkeypatch) -> None:
    async def loader(year):
        raise _FakeError("no key")

    mcp = SimpleNamespace(run=lambda: None)
    monkeypatch.setattr("sys.argv", ["mcpwright-x", "setup"])
    with pytest.raises(SystemExit) as exc:
        run_cli(mcp, loader=loader, error=_FakeError)
    assert exc.value.code == 1
