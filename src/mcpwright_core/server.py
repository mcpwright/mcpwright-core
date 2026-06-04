"""Server-side helpers shared across the mcpwright suite.

The bits every suite ``server.py`` repeats verbatim: the read-only tool annotation
applied to every tool, and the one-liner that pulls the lifespan-managed app context
out of an MCP request ``Context``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from mcp.types import ToolAnnotations

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context

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
