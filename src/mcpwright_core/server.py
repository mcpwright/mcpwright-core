"""Server-side helpers shared across the mcpwright suite.

The bits every suite ``server.py`` repeats: the read-only tool annotation applied
to every tool, the one-liner that pulls the lifespan-managed app context out of an
MCP request ``Context``, the lazy first-run load (double-checked lock), and the
``setup``/``refresh`` CLI dispatch fronting ``mcp.run()``.
"""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING, Any, cast

from mcp.types import ToolAnnotations

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine

    from mcp.server.fastmcp import Context, FastMCP

#: Annotation for every suite tool: read-only, and reaching the open web (the
#: one-time bulk load for store-backed servers, or live calls for others).
READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)


def app_context[T](ctx: Context, kind: type[T]) -> T:
    """The lifespan-managed app context, cast to the server's ``AppContext`` type.

    ``kind`` is the server's ``AppContext`` class; passing it lets the call site
    stay fully typed. Usage in a tool::

        app = app_context(ctx, AppContext)
    """
    return cast("T", ctx.request_context.lifespan_context)


async def ensure_loaded[T](
    lock: asyncio.Lock,
    *,
    is_loaded: Callable[[], bool],
    load: Callable[[], Awaitable[object]],
    version: Callable[[], T],
) -> T:
    """Lazily populate a local store on first use; return its loaded ``version``.

    The double-checked-lock pattern every store-backed server uses: cheap check
    first, then under ``lock`` re-check and ``load`` so concurrent first calls
    don't each kick off a download. ``version`` reads the loaded vintage / tax
    year (etc.) from the store afterwards.
    """
    if is_loaded():
        return version()
    async with lock:
        if not is_loaded():  # re-check inside the lock
            await load()
    return version()


def run_cli(
    mcp: FastMCP,
    *,
    loader: Callable[[int | None], Coroutine[Any, Any, object]],
    error: type[Exception],
    accepts_year: bool = False,
) -> None:
    """Console entry point for a store-backed server.

    With a ``setup`` / ``refresh`` argument, runs the one-time ``loader`` (an
    optional 4-digit year is parsed and passed when ``accepts_year``); otherwise
    runs the MCP server over stdio. ``error`` is the server's domain error: it's
    caught and printed as a clean message + exit 1 rather than a traceback.
    """
    argv = sys.argv
    if len(argv) > 1 and argv[1] in {"setup", "refresh"}:
        year: int | None = None
        if accepts_year and len(argv) > 2:
            try:
                year = int(argv[2])
            except ValueError:
                print(f"Not a valid year: {argv[2]!r}", file=sys.stderr)
                sys.exit(1)
        try:
            asyncio.run(loader(year))
        except error as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        return
    mcp.run()
