# Lessons Learned

_Updated as corrections are made during development._

## Environment

- **Always use `.venv/bin/python -m pytest`** to run tests. System `python` / `python3` does not have project dependencies. Don't try `python` or `python3` first — go straight to `.venv/bin/python`.

## Python Patterns

- **Never `from module import mutable_global`** — this copies the value at import time. If the global is reassigned later (e.g., during app startup/lifespan), the importing module keeps the stale original value. Always use `import module` and access `module.global_var` at runtime. This bit us with `compiled_graph`: routes imported `None` at startup and never saw the initialized graph.
  - Wrong: `from app.graph import compiled_graph` then `if compiled_graph is None`
  - Right: `import app.graph` then `if app.graph.compiled_graph is None`
  - Rule: If a module-level variable is set/mutated after import (singletons, lazy init, lifespan setup), consumers must access it via the module, not a direct import.

## Schema / Type Mismatches

- **Pydantic response schemas must match actual pipeline output types.** The `screenshots` field was typed as `dict | None` in `RunDetailResponse` but the pipeline produces a `list[dict]`. This caused a 500 on `GET /api/runs/{id}` even though the pipeline ran successfully. The DB model used `JSON` (accepts anything), masking the mismatch until runtime.
  - Rule: When defining Pydantic response schemas for JSON columns, verify the actual shape produced by the pipeline nodes — don't assume dict vs list.
  - Rule: After building a new pipeline node, trace the data shape from node output → DB storage → response schema to ensure consistency.

## Next.js / Frontend

- **When adding external image sources, update `next.config.mjs` `remotePatterns` for ALL hostnames that will serve images.** R2 has two URL patterns: `*.r2.cloudflarestorage.com` (S3 API) and `*.r2.dev` (public dev URL). We had the first but not the second, causing `next/image` to reject screenshots. Always check what URL the backend actually returns, not just the URL you configured in the backend.
  - Rule: When integrating any new image storage provider, verify the actual served hostname matches a `remotePatterns` entry before considering the feature done.

- **Never use `setTimeout` to defer `setState` calls during render.** This is a React anti-pattern that causes render flashes and race conditions. Instead, use `useEffect` with appropriate dependencies to initialize state when data arrives.
  - Wrong: `if (data && state === null) { setTimeout(() => setState(data.value), 0); }`
  - Right: `useEffect(() => { if (data) setState(data.value); }, [data]);`

- **Always add try/catch error handling to async handlers in React.** Every `async function handleX()` that calls an API should have try/catch with a user-facing error state. Silent failures (empty `catch {}`) leave users confused.
  - Rule: If a catch block only resets loading state, also set an error message.

- **When adding a union/literal type on backend schemas, update the corresponding frontend TypeScript type too.** We added `Literal["professional", ...]` to `settings.py` but initially forgot to update the frontend `UserSettings.default_tone` from `string` to a matching union type, causing a build error.
  - Rule: Backend schema changes → check frontend `types/index.ts` for matching interface.

## Docker / Deployment

- **Always pin base image versions in Dockerfiles** (e.g., `python:3.12.12-slim` not `python:3.12-slim`). Unpinned tags can break builds when upstream pushes a new minor version.
- **Always add a non-root user in Dockerfiles** (`RUN useradd --create-home appuser` + `USER appuser`). Running as root in containers is a security risk.
- **Always create a `.dockerignore`** to exclude `.git`, `.env`, `tests/`, `__pycache__`, `.venv` — reduces image size and prevents secrets from leaking into images.
