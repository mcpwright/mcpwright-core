# mcpwright-core

<!-- mcp-name: io.github.mcpwright/mcpwright-core -->

**The shared runtime toolkit for the [mcpwright](https://github.com/mcpwright) suite of MCP
servers.** Not a server itself — a small library the suite's servers
([edgar](https://github.com/mcpwright/edgar-mcp),
[census](https://github.com/mcpwright/census-mcp),
[soi](https://github.com/mcpwright/soi-mcp), …) depend on so they don't each re-implement the
same plumbing.

> Status: extracted once three servers existed and the seams were clear ("wait for two, then
> DRY"). Composable pieces — import what you need; no server uses all of it.

## What's in it

| Import | What it is |
|---|---|
| `AsyncHttpClient` | Async `httpx` base: descriptive User-Agent, retry + exponential backoff on transient failures (429 / 5xx / network), optional throttling, and a streaming `download_to(url, path)` for large files. Subclass it and add your endpoint methods. |
| `RateLimiter` | Serializes requests to a minimum spacing (`RateLimiter.per_second(8)`), for services with a fair-access policy like the SEC. |
| `TTLCache` | In-memory cache with per-entry TTL + a byte budget (LRU eviction). For servers that make live calls; bulk-download servers don't need it. |
| `READ_ONLY` | The `ToolAnnotations(readOnlyHint=True, openWorldHint=True)` every suite tool carries. |
| `app_context(ctx, AppContext)` | Pulls the lifespan-managed app context out of an MCP request `Context`. |
| `McpwrightError` / `HttpError` | The error hierarchy; each server's error type derives from these. |

## Usage

```python
from mcpwright_core import AsyncHttpClient, RateLimiter, HttpError

class MyError(HttpError):
    pass

class MyClient(AsyncHttpClient):
    USER_AGENT = "my-mcp (https://github.com/mcpwright/my-mcp)"

    def __init__(self) -> None:
        super().__init__(error_cls=MyError, rate_limiter=RateLimiter.per_second(8))

    async def widget(self, widget_id: str) -> dict:
        return await self.get_json(f"https://api.example.com/widgets/{widget_id}")
```

## Install

```bash
uv add mcpwright-core          # in a suite server's project
```

Servers pin a compatible range, e.g. `mcpwright-core>=0.1,<0.2`.

## Develop

```bash
uv sync
uv run ruff check src/ && uv run ruff format --check src/
uv run mypy
uv run pytest
```

Built to the suite engineering standard: ruff + mypy (strict-ish) + pytest + pre-commit, CI on
every PR, branch-protected `main`. Part of the [mcpwright](https://github.com/mcpwright) suite —
built by [Devender Gollapally](https://github.com/devender).
