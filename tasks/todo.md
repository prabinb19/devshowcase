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

- [ ] Craft LinkedIn system prompt (hook in first 210 chars, no links in body, 3K char limit, emoji-light)
- [ ] Build few-shot example bank: 10 high-performing LinkedIn dev posts as reference
- [ ] Implement `generate_posts` node — 2 LLM calls: analysis summary → LinkedIn post draft
- [ ] Generate alt text for each screenshot (accessibility, <125 chars)
- [ ] Generate LinkedIn first-comment text (contains GitHub link + brief CTA)
- [ ] Assemble `PostDraft` dataclass (body, first_comment, screenshot_urls, alt_texts, platform="linkedin")
- [ ] Write unit tests for generate node with fixture `ProjectAnalysis` inputs

---

## Section 7: Frontend — Core Pages

- [ ] Set up Next.js 14 App Router with `src/app/` structure
- [ ] Configure NextAuth.js with GitHub OAuth provider (sign in / sign out)
- [ ] Add auth middleware — protect all routes except landing page
- [ ] Build URL input page (`/dashboard`): paste GitHub URL, validate client-side, submit to `POST /api/runs`
- [ ] Build live status page (`/runs/[id]`): connect to SSE endpoint, show pipeline step progress
- [ ] Build review page (`/runs/[id]/review`):
  - [ ] Editable textarea for post body with character count (yellow at 90%, red at limit)
  - [ ] LinkedIn post preview mockup (looks like actual LinkedIn post)
  - [ ] Editable first-comment field for GitHub link
  - [ ] Screenshot gallery with selection checkboxes
- [ ] Build "Regenerate with feedback" flow — user types feedback, triggers new generate call
- [ ] Build "Save as Draft" — persist draft to DB, resume from `/drafts` page
- [ ] Build drafts list page (`/drafts`) — show saved drafts, resume editing
- [ ] Connect all frontend pages to FastAPI backend via `fetch` / SWR

---

## Section 8: OAuth + Publishing (LinkedIn Only)

- [ ] Apply for LinkedIn "Share on LinkedIn" developer product (manual step)
- [ ] Implement LinkedIn OAuth2 flow in backend (`w_member_social` scope)
- [ ] Store LinkedIn OAuth callback route and token exchange
- [ ] Build encrypted token storage using Fernet (encryption key from env var `TOKEN_ENCRYPTION_KEY`)
- [ ] Implement token refresh logic (60-day access token, 365-day refresh token)
- [ ] Implement LinkedIn image upload — 2-step: `initializeUpload` → `PUT` binary to upload URL
- [ ] Implement LinkedIn post creation via Posts API (v202502, `PUBLISHED` lifecycle state)
- [ ] Implement LinkedIn first-comment auto-post (comment on own post with GitHub link)
- [ ] Add retry logic with exponential backoff (max 3 retries, base 1s) for LinkedIn API calls
- [ ] Build post history page (`/history`) — show published posts with timestamps and LinkedIn links
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
