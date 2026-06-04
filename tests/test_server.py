from dataclasses import dataclass
from types import SimpleNamespace

from mcpwright_core.server import READ_ONLY, app_context


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
