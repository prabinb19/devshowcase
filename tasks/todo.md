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

- [ ] Implement GitHub URL validation with strict regex (`github.com/{owner}/{repo}`)
- [ ] Add SSRF prevention — reject private IPs, localhost, non-GitHub hosts
- [ ] Fetch repo metadata via GitHub REST API (`GET /repos/{owner}/{repo}`)
- [ ] Fetch and base64-decode README content (`GET /repos/{owner}/{repo}/readme`)
- [ ] Fetch recursive file tree (`GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1`, cap 10K entries)
- [ ] Fetch key config files: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `requirements.txt` (<50KB each)
- [ ] Extract image URLs from README markdown (regex for `![alt](url)` and `<img src>`)
- [ ] Assemble `RepoContext` dataclass with all fetched data
- [ ] Write unit tests for ingest node with fixture API responses (public repo, private repo, missing README)

---

## Section 4: Analyze Node (Claude LLM)

- [ ] Write analysis system prompt with prompt injection defenses (instruction hierarchy, output format lock)
- [ ] Implement `analyze_project` node using Anthropic SDK `client.messages.create()` directly
- [ ] Use `tool_use` to get structured `ProjectAnalysis` output (project name, summary, tech stack, highlights, category)
- [ ] Add README truncation to 8K tokens max before sending to LLM
- [ ] Cap file tree at 500 entries before sending to LLM
- [ ] Implement screenshot strategy determination (web app → sandbox, has README images → extract, fallback → project card)
- [ ] Add content moderation check — filter secrets, API keys, credentials from context before LLM call
- [ ] Write unit tests for analyze node with fixture `RepoContext` inputs

---

## Section 5: Capture Node (Screenshots)

- [ ] Build custom E2B template Dockerfile (Node 20, Python 3.12, Playwright, Chromium)
- [ ] Register E2B template and store template ID in config
- [ ] Implement Strategy A: extract image URLs from README, download and validate (must be real images, <5MB)
- [ ] Implement Strategy B: sandbox screenshot for web apps
  - [ ] Detect framework from `package.json` (Next.js, Vite, CRA, etc.)
  - [ ] Generate install + build + preview commands per framework
  - [ ] Run `npm install && npm run build && npm run preview` in E2B sandbox
  - [ ] Wait for server ready with `domcontentloaded` + fixed wait (not `networkidle`)
  - [ ] Take screenshots at 1s, 3s, 5s intervals — pick sharpest/largest
  - [ ] Enforce 5-minute sandbox hard limit
- [ ] Implement Strategy D: generate project card via Satori (`1200x630px`, project name + tech stack + description)
- [ ] Implement fallback chain: sandbox → README images → project card
- [ ] Add image post-processing: resize to max 2048px wide, compress to <1MB, normalize to JPG
- [ ] Set up Cloudflare R2 bucket and configure S3-compatible credentials
- [ ] Implement R2 upload function — upload processed images, return public URLs
- [ ] Write integration tests with 10 diverse repos (React app, Python CLI, Rust lib, Go service, etc.)

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
