# mcpwright-core — working agreement

`mcpwright-core` is the **shared runtime library** for the **mcpwright** suite
(`github.com/mcpwright`). It is **not a server** — it has no MCP tools. The suite's servers
(edgar / census / soi / …) depend on it so they don't each re-implement the same plumbing.

> The full suite rubric is
> `~/my-notes/professional-self-improvement/mcpwright/mcp-standards.md`; the extraction
> rationale is `mcpwright-core-plan.md`. The reference *server* is `edgar-mcp`.

## What this library is (and isn't)

- **Composable pieces, not a monolith.** No server uses all of it: edgar uses the HTTP client +
  `TTLCache`; census/soi use the HTTP client + (later) the store/CLI helpers. Add a piece only
  when a real server needs it — don't speculatively abstract.
- **It is a public-API boundary.** Three servers import it, so signatures, types, and behavior
  are a contract. Prefer backwards-compatible changes; a breaking change to a base class means a
  coordinated PR across every consumer. Public types must be precise (mypy strict across the
  boundary).

## Non-negotiable policies

- **Lots of unit tests, all I/O mocked** (`respx` for HTTP). New behavior ships with its tests
  in the same PR. `pytest` green before a PR opens.
- **Latest patterns.** Python 3.12+ idioms (PEP 695 generics, `from __future__ import
  annotations`), `uv` for deps + build, async `httpx`. Official `mcp` SDK via
  `mcp.server.fastmcp` where server helpers touch it.
- **PR per change, CI-gated.** feature branch → code → **code-reviewer** subagent
  (`.claude/agents/code-reviewer.md`, or `/review-pr`) → fold in findings → PR → `Code Quality
  & Tests` green → squash-merge `(#N)`. `main` is branch-protected; no direct pushes. Commits:
  imperative subject + short body + the `Co-authored-by` trailer.
- **Green locally before pushing:**
  ```bash
  uv run ruff check src/ && uv run ruff format --check src/ && uv run mypy && uv run pytest
  ```
  `uv run pre-commit run --all-files` mirrors CI.

## Layout

```
src/mcpwright_core/
  __init__.py   # re-exports the public API
  errors.py     # McpwrightError -> HttpError hierarchy
  cache.py      # TTLCache: in-memory TTL + byte-budgeted LRU
  http.py       # AsyncHttpClient + RateLimiter: retry/backoff base; download_to() streaming
  server.py     # READ_ONLY annotation + app_context(ctx, AppContext) accessor
tests/          # respx-mocked; one file per module
```

## Publishing

PyPI dist `mcpwright-core` (import `mcpwright_core`). It's a **library**, so: no MCP Registry
entry, no MCPB bundle, no `[project.scripts]`. Build + publish with `uv build` / `uv publish`
(token in `~/my-notes/pypi.txt`); bump `version` in `pyproject.toml` **and** `__version__` in
`__init__.py` together. Servers pin `mcpwright-core>=0.1,<0.2`.
