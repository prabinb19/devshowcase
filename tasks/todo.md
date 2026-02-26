# DevShowcase — Task Breakdown

> Auto-generated from `high-level-plan.md` and `overview-plan.md`.
> Overview-plan refinements applied: Postgres (Neon), Cloudflare R2, LinkedIn-only MVP, Railway hosting.

---

## Section 1: Project Setup

- [x] Create monorepo root with top-level README and `.gitignore`
- [x] Initialize Python backend (`backend/pyproject.toml` with FastAPI, LangGraph, Anthropic SDK, SQLAlchemy, Alembic, E2B, httpx)
- [x] Create backend directory structure (`backend/app/`, `nodes/`, `models/`, `routes/`, `services/`)
- [x] Initialize Next.js 14 frontend (`frontend/` with App Router, Tailwind CSS, NextAuth.js)
- [x] Create `docker-compose.yml` for local Postgres (port 5432)
- [x] Create `.env.example` for backend (DB URL, API keys, R2 creds, encryption key)
- [x] Create `.env.example` for frontend (NextAuth secret, GitHub OAuth, backend URL)
- [ ] Set up Neon Postgres free-tier database for dev/prod _(manual step)_
- [x] Define SQLAlchemy models: `User`, `Run`, `Draft`, `Token`
- [x] Configure Alembic and generate initial migration
- [x] Run migration against local Postgres and verify tables (4 tables + alembic_version confirmed)

---

## Section 2: Backend Core (FastAPI + LangGraph)

- [x] Create FastAPI app entry point (`backend/app/main.py`) with CORS config
- [x] Define LangGraph `AgentState` TypedDict and Pydantic data models (`backend/app/state.py`)
- [x] Build LangGraph graph definition (`backend/app/graph.py`) with nodes: ingest → analyze → capture → generate
- [x] Configure PostgresSaver checkpointer for graph state persistence
- [x] Create `POST /api/runs` endpoint — accepts GitHub URL, starts pipeline run, returns run ID
- [x] Create `GET /api/runs/{id}` endpoint — returns run status and results
- [x] Create `GET /api/runs/{id}/stream` SSE endpoint for live pipeline status (15s heartbeat)
- [x] Add global error handler node to graph (catches exceptions, sets `error` field on state)
- [x] Add per-user rate limiting middleware (10 runs/hr, 429 response)
- [x] Write tests for API endpoints with mocked graph execution

---

## Section 3: Ingest Node (GitHub API)

- [x] Implement GitHub URL validation with strict regex (`github.com/{owner}/{repo}`)
- [x] Add SSRF prevention — reject private IPs, localhost, non-GitHub hosts
- [x] Fetch repo metadata via GitHub REST API (`GET /repos/{owner}/{repo}`)
- [x] Fetch and base64-decode README content (`GET /repos/{owner}/{repo}/readme`)
- [x] Fetch recursive file tree (`GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1`, cap 10K entries)
- [x] Fetch key config files: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `requirements.txt` (<50KB each)
- [x] Extract image URLs from README markdown (regex for `![alt](url)` and `<img src>`)
- [x] Assemble `RepoContext` dataclass with all fetched data
- [x] Write unit tests for ingest node with fixture API responses (public repo, private repo, missing README)

---

## Section 4: Analyze Node (Claude LLM)

- [x] Write analysis system prompt with prompt injection defenses (instruction hierarchy, output format lock)
- [x] Implement `analyze_project` node using Anthropic SDK `client.messages.create()` directly
- [x] Use `tool_use` to get structured `ProjectAnalysis` output (project name, summary, tech stack, highlights, category)
- [x] Add README truncation to 8K tokens max before sending to LLM
- [x] Cap file tree at 500 entries before sending to LLM
- [x] Implement screenshot strategy determination (web app → sandbox, has README images → extract, fallback → project card)
- [x] Add content moderation check — filter secrets, API keys, credentials from context before LLM call
- [x] Write unit tests for analyze node with fixture `RepoContext` inputs

---

## Section 5: Capture Node (Screenshots)

- [ ] Build custom E2B template Dockerfile (Node 20, Python 3.12, Playwright, Chromium) _(deferred — ops task)_
- [ ] Register E2B template and store template ID in config _(deferred — ops task)_
- [x] Implement Strategy A: extract README images — download up to 3, validate, process, upload to R2
- [ ] Implement Strategy B: sandbox screenshot for web apps _(MVP: falls back to project card; needs E2B Desktop)_
  - [ ] Detect framework from `package.json` (Next.js, Vite, CRA, etc.)
  - [ ] Generate install + build + preview commands per framework
  - [ ] Run `npm install && npm run build && npm run preview` in E2B sandbox
  - [ ] Wait for server ready with `domcontentloaded` + fixed wait (not `networkidle`)
  - [ ] Take screenshots at 1s, 3s, 5s intervals — pick sharpest/largest
  - [ ] Enforce 5-minute sandbox hard limit
- [x] Implement Strategy C: generate project card via Pillow (`1200x630px`, dark slate, project name + tech stack + features)
- [x] Implement fallback chain: sandbox → project card, readme_images → project card if empty
- [x] Add image post-processing: resize to max 1200px, compress, RGBA→RGB for JPEG
- [ ] Set up Cloudflare R2 bucket and configure S3-compatible credentials _(manual step)_
- [x] Implement R2 upload function — lazy singleton boto3 client, content-hash dedup, public URL return
- [x] Replace capture node stub with strategy router (reads `screenshot_strategy` from analysis)
- [x] Write unit tests for capture node and all screenshot services (29 tests)

---

## Section 6: Generate Node (LinkedIn Post Drafts)

- [x] Craft LinkedIn system prompt (hook in first 210 chars, no links in body, 3K char limit, emoji-light)
- [x] Build few-shot example bank: 3 concise examples demonstrating desired style (CLI tool, web app, library)
- [x] Implement `generate` node — single Claude tool_use call producing body, first_comment, and alt_texts
- [x] Generate alt text for each screenshot inline (accessibility, ≤125 chars, truncated)
- [x] Generate LinkedIn first-comment text (contains GitHub link + brief CTA, ≤500 chars)
- [x] Assemble `PostDraft` via Pydantic model (body, first_comment, screenshot_urls, alt_texts, platform="linkedin")
- [x] Write unit tests for generate node (14 tests: schema, user message, integration, content validation)

---

## Section 7: Frontend — Core Pages

- [x] Backend: Added `post_draft` JSON column to Run model + alembic migration 002
- [x] Backend: Created `get_or_create_user` dependency, updated runs to use GitHub ID headers
- [x] Backend: Draft CRUD routes (POST/GET list/GET/PATCH/DELETE) + schemas
- [x] Backend: Regenerate endpoint (`POST /api/runs/{run_id}/regenerate`)
- [x] Backend: 14 tests passing (8 draft + 6 run tests)
- [x] Configure NextAuth.js with GitHub OAuth provider (JWT/session callbacks for githubId)
- [x] Add auth middleware — protect `/dashboard`, `/runs`, `/drafts` routes
- [x] Build TypeScript types, API client, useUser/useSSE hooks, SWR installed
- [x] Build UI primitives: Button (variants/loading), Input (label/error), Card, Navbar
- [x] Build landing page (`/`) — hero, 3-step explainer, "Sign in with GitHub" button
- [x] Build URL input page (`/dashboard`): paste GitHub URL, validate client-side, submit to `POST /api/runs`
- [x] Build live status page (`/runs/[id]`): SSE + SWR polling, vertical stepper with stage icons
- [x] Build review page (`/runs/[id]/review`):
  - [x] Two-column editor/preview layout
  - [x] Editable textarea for post body with character count (yellow at 2700, red at 3000)
  - [x] LinkedIn post preview mockup (avatar, name, body, screenshots, action row)
  - [x] Editable first-comment field
  - [x] Screenshot gallery with selection checkboxes and editable alt texts
- [x] Build "Regenerate with feedback" flow — modal with feedback textarea, triggers regenerate endpoint
- [x] Build "Save as Draft" — persist draft to DB via CRUD API, navigates to `/drafts`
- [x] Build drafts list page (`/drafts`) — SWR-fetched cards with delete action, empty state
- [x] Connect all frontend pages to FastAPI backend via centralized API client + SWR

---

## Section 8: OAuth + Publishing (LinkedIn Only)

- [ ] Apply for LinkedIn "Share on LinkedIn" developer product (manual step)
- [x] Implement LinkedIn OAuth2 flow in backend (`w_member_social` scope)
- [x] Store LinkedIn OAuth callback route and token exchange
- [x] Build encrypted token storage using Fernet (encryption key from env var `TOKEN_ENCRYPTION_KEY`)
- [x] Implement token refresh logic (60-day access token, 365-day refresh token)
- [x] Implement LinkedIn image upload — 2-step: `initializeUpload` → `PUT` binary to upload URL
- [x] Implement LinkedIn post creation via Posts API (v202502, `PUBLISHED` lifecycle state)
- [x] Implement LinkedIn first-comment auto-post (comment on own post with GitHub link)
- [x] Add retry logic with exponential backoff (max 3 retries, base 1s) for LinkedIn API calls
- [x] Build post history page (`/history`) — show published posts with timestamps and LinkedIn links
- [ ] End-to-end test: GitHub URL → pipeline → review → publish to LinkedIn

---

## Section 9: Polish & Launch

- [ ] Build landing page (`/`) — hero section, how it works, demo GIF, security philosophy
- [ ] Add error states and empty states throughout UI (failed runs, no drafts, API errors)
- [ ] Make review UI mobile-responsive (responsive textarea, stacked layout on small screens)
- [ ] Add user preferences page (`/settings`) — default tone, hashtag preferences
- [ ] Write project README with setup instructions, architecture diagram, contributing guide
- [ ] Deploy backend to Railway (Dockerfile, env vars, Postgres addon or Neon connection)
- [ ] Deploy frontend to Vercel (env vars, custom domain optional)
- [ ] Showcase DevShowcase using itself — generate a LinkedIn post about the project
- [ ] Open source the repository

---

## Review

### Section 1 Review (2026-02-25)

**Completed:**
- Monorepo scaffolded: root README, .gitignore, docker-compose.yml
- Backend: pyproject.toml, FastAPI app with CORS + /health, pydantic Settings, async SQLAlchemy engine
- Frontend: Next.js 14 (App Router, TypeScript, Tailwind, ESLint) + next-auth
- SQLAlchemy models: User, Run (7-status enum), Draft, Token — 4 tables with UUID PKs
- Alembic: async env.py, hand-written migration `001_initial_tables.py`, verified SQL output
- Both .env.example files with all required variables

**Remaining manual step:**
- Neon Postgres setup for prod (connection string format documented in .env.example)

**Notes:**
- Python 3.12 installed via Homebrew, venv at `backend/.venv`
- Fixed pyproject.toml build-backend (was wrong path) and added package discovery config
- Frontend nested .git removed for monorepo structure
- Local Homebrew postgresql@16 was conflicting on port 5432 — stopped it to use Docker container
- `alembic upgrade head` ran successfully: users, runs, drafts, tokens, alembic_version tables confirmed

### Section 2 Review (2026-02-25)

**Completed (13 items):**
- `psycopg[binary,pool]` added to pyproject.toml for LangGraph checkpointer
- `checkpoint_url` (psycopg3 format) and `rate_limit_runs_per_hour` added to Settings
- Pydantic models: RepoMetadata, RepoContext, ProjectAnalysis, Screenshot, PostDraft, PublishResult
- LangGraph AgentState TypedDict with all pipeline fields
- 4 stub nodes (ingest, analyze, capture, generate) with `get_stream_writer()` SSE support
- Error handler node — writes failure to DB Run record (real implementation)
- StateGraph wired: ingest → analyze → capture → generate with conditional error routing
- AsyncPostgresSaver checkpointer with lifespan init/shutdown
- Schemas: CreateRunRequest, RunResponse, RunDetailResponse
- Background executor via `asyncio.create_task()` — updates Run in DB on completion/failure
- DB-backed rate limit middleware on `POST /api/runs` (X-User-Id header, 10/hr)
- 3 API endpoints: POST /api/runs (202), GET /api/runs/{id}, GET /api/runs/{id}/stream (SSE)
- FastAPI main.py updated with lifespan, router, middleware
- `.env.example` updated with CHECKPOINT_URL
- 4 tests passing: create run (202), get run not found (404), get run found (200), rate limit (429)

**Architecture:**
- Two Postgres drivers coexist: asyncpg (SQLAlchemy) + psycopg3 (LangGraph checkpointer)
- `compiled_graph` is a module-level singleton initialized during FastAPI lifespan
- pytest-asyncio set to `auto` mode in pyproject.toml

### Section 3 Review (2026-02-25)

**Completed (9 items):**
- `backend/app/services/github_client.py` — new shared async GitHub API client
  - `parse_github_url()` with strict regex for `github.com/{owner}/{repo}` (supports `.git` suffix, trailing slash)
  - `_validate_url()` SSRF prevention — only allows `github.com` / `www.github.com` hosts, rejects private/loopback IPs
  - `_get_client()` lazy singleton `httpx.AsyncClient` with Bearer token auth, 30s timeout
  - `fetch_repo_metadata()` — maps API response to RepoMetadata dict shape
  - `fetch_readme()` — base64-decodes content, returns `""` on 404
  - `fetch_file_tree()` — recursive tree capped at 10K entries, falls back from `main` to `master` branch
  - `fetch_config_files()` — fetches 5 known config files if present in tree and <50KB
  - `extract_readme_images()` — regex for `![alt](url)` and `<img src="url">` with deduplication
- `backend/app/nodes/ingest.py` — replaced stub with real implementation
  - Validates URL, fetches all data, assembles `repo_context` dict
  - Error propagation via `error` key in state (triggers graph error_handler routing)
  - Handles `HTTPStatusError` (404/403/etc) and `HTTPError` (network) with descriptive messages
- `backend/tests/test_ingest.py` — 29 unit tests, all passing
  - URL parsing (9), SSRF prevention (4), fetch functions (9), image extraction (4), ingest node integration (3)
  - All tests use mocked httpx — no real API calls, no GitHub token required

**Architecture:**
- All GitHub API logic in `services/github_client.py`, ingest node is a thin orchestrator
- Module-level `httpx.AsyncClient` singleton reuses connection pool across requests
- SSRF check is host-based only (no DNS resolution needed since we restrict to github.com)

**Test suite:** 33 total tests passing (29 new + 4 existing from Section 2)

### Section 4 Review (2026-02-25)

**Completed (8 items):**
- `backend/app/services/llm_client.py` — new lazy singleton Anthropic client
  - `get_anthropic_client()` mirrors `github_client.py` pattern with `settings.anthropic_api_key`
  - Reusable for future nodes (generate, etc.)
- `backend/app/prompts/analyze.py` — system prompt with security defenses
  - Instruction hierarchy: repo content marked as untrusted data, not instructions
  - Output format locked to `extract_project_analysis` tool_use only
  - Analysis rules for all ProjectAnalysis fields (project_type enum, visual_type classification, etc.)
- `backend/app/prompts/__init__.py` — re-exports `ANALYZE_SYSTEM_PROMPT`
- `backend/app/nodes/analyze.py` — replaced stub with real Claude-powered implementation
  - `_redact_secrets()` — regex patterns for AWS keys, GitHub PATs, OpenAI keys, PEM keys, generic credentials
  - `_truncate_readme()` — caps at 32K chars (~8K tokens at 4 chars/token)
  - `_cap_file_tree()` — limits to 500 entries
  - `_determine_screenshot_strategy()` — deterministic: web→sandbox, has images→readme_images, fallback→project_card
  - `_build_tool_schema()` — derives from `ProjectAnalysis.model_json_schema()`, excludes `screenshot_strategy`
  - `_build_user_message()` — assembles metadata + redacted README + capped tree + redacted configs
  - `analyze()` — calls Claude (`claude-sonnet-4-20250514`) with forced tool_use, validates via Pydantic, returns structured analysis
  - Error handling returns `{"error": ..., "current_stage": "analyzing"}` (same pattern as ingest)
- `backend/tests/test_analyze.py` — 21 unit tests, all passing
  - Secret redaction (6): AWS keys, GitHub PATs, OpenAI keys, PEM keys, generic credentials, normal text preserved
  - README truncation (2): short unchanged, long truncated with marker
  - File tree capping (2): under limit unchanged, over limit capped to 500
  - Screenshot strategy (4): web→sandbox, has images→readme_images, fallback→project_card, web priority over images
  - Tool schema (2): has required fields, excludes screenshot_strategy
  - Node integration (5): success, missing repo_context, API error, no tool_use block, web visual_type→sandbox strategy

**Architecture:**
- Anthropic client in `services/llm_client.py` — reusable singleton for Section 6 generate node
- Token counting via char estimate (4 chars/token) — avoids tiktoken dependency
- Screenshot strategy is deterministic code, not LLM — simple rules don't need LLM tokens
- Secret redaction runs before LLM call — regex-based on README and config contents
- Tool schema derived from Pydantic `model_json_schema()` — stays in sync automatically
- Model: `claude-sonnet-4-20250514` — cost-effective for analysis

**Test suite:** 54 total tests passing (21 new + 33 existing from Sections 1-3)

### Section 5 Review (2026-02-25)

**Completed (7 items, 29 tests):**
- `backend/app/services/image_processor.py` — Pillow-based image utilities
  - `validate_image()` — verify bytes are a valid image via PIL verify
  - `get_dimensions()` — return (width, height) tuple
  - `process_image()` — resize preserving aspect ratio, RGBA→RGB for JPEG, compress with optimize
- `backend/app/services/r2_storage.py` — Cloudflare R2 upload client
  - `_get_r2_client()` lazy singleton boto3 S3 client using `settings.r2_*` credentials
  - `upload_image()` — uploads to `screenshots/{run_id}/{content_hash}_{filename}`, returns public URL
  - Content-hash (SHA-256 prefix) in key for free deduplication
- `backend/app/services/screenshot/` — strategy pattern package
  - `readme_images.py` — downloads up to 3 README images, resolves relative/blob GitHub URLs, validates, processes, uploads
  - `project_card.py` — Pillow-rendered 1200×630 LinkedIn card (dark slate bg, blue accent, name, description, tech tags, features, stars/language)
  - `sandbox.py` — MVP stub that logs and falls back to `generate_project_card()`, documented for future E2B Desktop
  - `__init__.py` — re-exports all three strategies
- `backend/app/nodes/capture.py` — replaced stub with strategy router
  - Reads `screenshot_strategy` from analysis, dispatches to appropriate service
  - Builds common `card_kwargs` from metadata + analysis for project card / sandbox
  - Fallback: readme_images → project_card if no valid images captured
  - Error handling returns `{"error": ..., "current_stage": "capturing"}`
- `backend/tests/test_capture.py` — 29 unit tests
  - Image processor (5): validate valid/invalid/empty, resize with aspect ratio, RGBA→RGB for JPEG
  - R2 storage (3): put_object called, returns URL, content-hash dedup
  - URL resolution (4): absolute unchanged, relative resolved, blob converted, dot-slash handled
  - README images (4): happy path, skip invalid, cap at 3, handle download failure
  - Project card (2): generates valid PNG 1200×630, handles missing fields
  - Sandbox (1): falls back to project card
  - Capture node (6): routes to project_card/sandbox/readme_images, readme fallback, missing analysis/repo_context errors

**Architecture:**
- Strategy pattern: `services/screenshot/` package, capture node is thin router (consistent with ingest/analyze)
- Sandbox stub in `sandbox.py` — only this file changes when E2B Desktop is integrated
- boto3 synchronous for MVP — images <1MB, blocking negligible; `asyncio.to_thread()` later if needed
- Pillow for project cards — no Satori/Node.js dependency needed
- 3-image cap for README — limits cost and processing time

**Deferred items:**
- E2B template Dockerfile and registration (ops task)
- Real sandbox screenshots via E2B Desktop + Playwright (only touches `sandbox.py`)
- Cloudflare R2 bucket setup (manual step)

**Test suite:** 83 total tests passing (29 new + 54 existing from Sections 1-4)

### Section 6 Review (2026-02-25)

**Completed (7 items, 14 tests):**
- `backend/app/prompts/generate.py` — LinkedIn post generation system prompt
  - Instruction hierarchy: project data marked as untrusted, output locked to `generate_linkedin_post` tool_use
  - LinkedIn rules: hook in first 210 chars, no links in body, max 3000 chars, emoji-light, line breaks
  - First comment rules: repo link + CTA, <500 chars
  - Alt text rules: descriptive, ≤125 chars, accessibility-focused
  - 3 few-shot examples (CLI tool, web app, library) — concise, stays within token budget
- `backend/app/prompts/__init__.py` — added `GENERATE_SYSTEM_PROMPT` to re-exports
- `backend/app/nodes/generate.py` — replaced stub with Claude-powered implementation
  - `_build_tool_schema()` — derives from `PostDraft.model_json_schema()`, keeps only `body`, `first_comment`, `alt_texts`
  - `_build_user_message()` — assembles project overview, tech stack, key features, screenshot descriptions, repo URL
  - `generate()` — calls Claude (`claude-sonnet-4-20250514`) with forced tool_use, validates/clamps content lengths, assembles `PostDraft`
  - Content clamping: body ≤3000, first_comment ≤500, alt_texts ≤125 chars each
  - Screenshot URLs set programmatically from state (not LLM-generated)
  - Error handling for missing analysis, missing screenshots, API errors, no tool_use block
- `backend/tests/test_generate.py` — 14 unit tests
  - Tool schema (2): expected fields present, programmatic fields excluded
  - User message (4): project info, repo URL, screenshots, key features
  - Node integration (5): success, missing analysis, missing screenshots, API error, no tool_use block
  - Content validation (3): body truncation, alt text truncation, empty screenshots

**Architecture:**
- Single LLM call (not two) — analysis already provides quality summary, second pass adds latency without value
- Tool schema derived from `PostDraft` Pydantic model — same pattern as analyze node
- Programmatic fields (`platform`, `status`, `screenshot_urls`) set in code, not by LLM
- 3 few-shot examples (not 10) — sufficient to demonstrate style while staying within token budget

**Test suite:** 97 total tests passing (14 new + 83 existing from Sections 1-5)

### Section 7 Review (2026-02-25)

**Backend changes (Part A — 8 files):**
- `backend/app/models/base.py` — added `post_draft` JSON column to Run model
- `backend/app/services/run_executor.py` — saves `post_draft` from final state; new `execute_graph_from_generate()` for regeneration
- `backend/app/schemas/runs.py` — added `post_draft` to `RunDetailResponse`
- `backend/app/schemas/drafts.py` — NEW: `CreateDraftRequest`, `UpdateDraftRequest`, `DraftResponse`
- `backend/app/routes/deps.py` — NEW: `get_or_create_user(github_id, github_username, session) -> User`
- `backend/app/routes/runs.py` — switched from UUID X-User-Id to GitHub ID headers; added regenerate endpoint
- `backend/app/routes/drafts.py` — NEW: full CRUD router (POST/GET list/GET/PATCH/DELETE)
- `backend/app/main.py` — registered drafts router
- `backend/alembic/versions/002_add_post_draft_column.py` — NEW migration
- `backend/tests/test_drafts.py` — NEW: 8 tests for draft CRUD
- `backend/tests/test_runs.py` — updated for new headers + 2 regenerate tests

**Frontend changes (Parts B-E — 16 files):**
- Auth: `lib/auth.ts`, `lib/session-provider.tsx`, `middleware.ts`, `api/auth/[...nextauth]/route.ts`
- Types/API: `types/index.ts`, `lib/api.ts`, `lib/hooks.ts`
- UI: `components/ui/button.tsx`, `components/ui/input.tsx`, `components/ui/card.tsx`, `components/navbar.tsx`
- Pages: `app/page.tsx` (landing), `app/landing-content.tsx`, `app/dashboard/page.tsx`, `app/runs/[id]/page.tsx`, `app/runs/[id]/review/page.tsx`, `app/drafts/page.tsx`
- Config: `next.config.mjs` (image patterns), `globals.css` (stepper animation), `app/layout.tsx` (AuthSessionProvider)
- Dependency: `swr` added

**Architecture:**
- NextAuth 4 with GitHub provider, JWT strategy, githubId/githubUsername persisted in session
- Middleware protects `/dashboard`, `/runs`, `/drafts` routes
- Centralized `apiFetch` wrapper in `lib/api.ts` — all API calls go through it
- `useSSE` hook manages EventSource lifecycle; `useUser` hook provides typed session data
- Review page stores `user_id` (UUID) in localStorage for drafts page consumption
- Direct SSE to backend (not proxied through Next.js API routes)

**Verification:**
- Backend: 14/14 tests pass (`pytest tests/test_runs.py tests/test_drafts.py -v`)
- Frontend: `npx next build` succeeds — all 5 routes + auth handler compiled, no TS/ESLint errors

**Test suite:** 111 total tests passing (14 new backend + 97 existing from Sections 1-6)

### Section 8 Review (2026-02-26)

**Backend changes (7 files created, 3 modified):**
- `backend/app/services/token_encryption.py` — NEW: Fernet encrypt/decrypt with lazy singleton pattern (matches `r2_storage.py`)
- `backend/app/schemas/linkedin.py` — NEW: `LinkedInAuthURLResponse`, `LinkedInCallbackRequest`, `LinkedInTokenStatus`, `PublishRequest`, `PublishResponse`
- `backend/app/services/linkedin_client.py` — NEW: Full LinkedIn API client (~200 lines)
  - `_request_with_retry()` — exponential backoff (max 3, base 1s) for 5xx/429
  - `build_auth_url(state)` — OAuth URL with `w_member_social openid profile` scope
  - `exchange_code_for_tokens(code)` — POST to token endpoint
  - `refresh_access_token(refresh_token)` — refresh flow
  - `get_linkedin_profile(access_token)` — GET `/v2/userinfo`, returns person URN
  - `upload_image(access_token, author_urn, image_url)` — 2-step: `initializeUpload` then PUT binary
  - `create_post(access_token, author_urn, body, image_urns)` — Posts API v202502, single/multi-image support
  - `create_comment(access_token, post_urn, text)` — comment on own post
  - All calls use `LinkedIn-Version: 202502` header and `httpx.AsyncClient`
- `backend/app/routes/linkedin.py` — NEW: 5 endpoints
  - `GET /api/linkedin/auth-url` — returns OAuth redirect URL
  - `POST /api/linkedin/callback` — exchanges code for tokens, encrypts, upserts Token row
  - `GET /api/linkedin/status` — checks valid LinkedIn token (auto-refreshes if expired)
  - `POST /api/linkedin/publish` — upload images → create post → auto-comment → update draft status
  - `DELETE /api/linkedin/disconnect` — removes stored tokens (204)
- `backend/app/config.py` — added `linkedin_redirect_uri` setting
- `backend/app/main.py` — registered linkedin router
- `backend/app/routes/drafts.py` — added optional `status: DraftStatus | None` query filter to `list_drafts`
- `backend/tests/test_linkedin.py` — NEW: 10 tests
  - Token encryption round-trip, auth URL, callback stores token, status connected/not connected
  - Publish success (mocked LinkedIn API), publish no token (401), publish draft not found (404)
  - Retry logic (500 then 200), disconnect (204)

**Frontend changes (2 files created, 5 modified):**
- `frontend/src/app/api/linkedin/callback/route.ts` — NEW: Next.js API route catches LinkedIn OAuth redirect, forwards code to backend
- `frontend/src/app/history/page.tsx` — NEW: Published posts page with card grid, SWR fetch with `status=published` filter
- `frontend/src/types/index.ts` — added `LinkedInStatus`, `PublishResponse` interfaces
- `frontend/src/lib/api.ts` — added `getLinkedInAuthUrl()`, `getLinkedInStatus()`, `publishToLinkedIn()`, `disconnectLinkedIn()`, `listDraftsByStatus()`
- `frontend/src/app/runs/[id]/review/page.tsx` — added "Publish to LinkedIn" button with connection check flow (save draft → publish → redirect to /history)
- `frontend/src/components/navbar.tsx` — added "History" nav link
- `frontend/src/middleware.ts` — added `/history/:path*` to protected routes

**Architecture:**
- Token encryption uses `cryptography.Fernet` — same lazy singleton pattern as R2 client
- LinkedIn API client is standalone in `services/linkedin_client.py` — routes are thin orchestrators
- Auto-refresh: status and publish endpoints transparently refresh expired tokens
- Frontend publish flow: checks connection → redirects to OAuth if needed → saves draft → publishes → redirects to history
- History page reuses existing drafts API with new `status` filter parameter

**Deferred items:**
- LinkedIn developer product application (manual step)
- End-to-end test (requires live LinkedIn credentials)

**Verification:**
- Backend: 10/10 new tests pass, 117/117 total tests pass
- Frontend: `npx next build` succeeds — all routes compiled, no TS/ESLint errors

**Test suite:** 117 total tests passing (10 new + 107 existing from Sections 1-7)

### Section 9 Quality Fixes Review (2026-02-26)

**Critical fixes (2):**
- `review/page.tsx` — Replaced `setTimeout` setState anti-pattern with `useEffect` keyed on `[draft]` for initializing screenshots/altTexts. Removed dead empty `if` block.
- `settings/page.tsx` — Added try/catch error handling to `handleSave`, `handleConnectLinkedIn`, `handleDisconnectLinkedIn` with user-facing error display.

**High fixes (4):**
- `review/page.tsx` — Added `error` state with user-facing messages in `handleSaveDraft` and `handleRegenerate` catch blocks, displayed in UI.
- `backend/Dockerfile` — Pinned base image to `python:3.12.12-slim`, added non-root `appuser` (security hardening).
- `backend/.dockerignore` — NEW: excludes `.git`, `__pycache__`, `.env`, `tests/`, `*.pyc`, `.venv`.
- `backend/tests/test_settings.py` — NEW: 5 tests (GET defaults, GET stored, PUT update, PUT invalid tone 422, missing auth 422).

**Medium fixes (3):**
- `backend/app/schemas/settings.py` — Constrained `default_tone` to `Literal["professional", "casual", "technical", "enthusiastic"]`, added `max_length=30` on hashtags list, removed unused `from_attributes`.
- `frontend/src/types/index.ts` — Added `ToneOption` union type, applied to `UserSettings.default_tone`.
- `settings/page.tsx` — Added duplicate hashtag prevention in `addHashtag()`, typed tone state as `ToneOption`.

**Files modified (5):** `review/page.tsx`, `settings/page.tsx`, `types/index.ts`, `schemas/settings.py`, `Dockerfile`
**Files created (2):** `backend/.dockerignore`, `backend/tests/test_settings.py`

**Verification:**
- Backend: 122/122 tests pass (5 new settings tests + 117 existing)
- Frontend: `npx next build` succeeds — no TS/ESLint errors

**Test suite:** 122 total tests passing (5 new + 117 existing from Sections 1-8)
