# DevShowcase Architecture

## System Overview

DevShowcase is a web app that transforms GitHub repositories into polished LinkedIn posts using an autonomous AI agent running inside an E2B sandbox.

## High-Level Flow

```
User pastes repo URL → Backend creates Run → Spins up E2B sandbox →
Agent clones repo → Analyzes code → Extracts images → Gemini generates post →
Results written to sandbox files → Backend polls & streams via SSE → User reviews/publishes
```

## Backend (FastAPI — Agent Gateway)

The backend is a thin orchestration layer. It does NOT run AI models directly.

### Key Services
- `agent_executor.py` — Core orchestrator. Manages sandbox lifecycle, file-based IPC, SSE event queues
- `github_client.py` — GitHub API for auth
- `r2_storage.py` — Cloudflare R2 image storage
- `linkedin_client.py` — LinkedIn OAuth + publishing
- `image_processor.py` — Image processing utilities
- `token_encryption.py` — Fernet encryption for stored tokens

### Agent Executor Internals
Three in-memory dicts coordinate sandbox lifecycle:
- `_agent_events: dict[str, asyncio.Queue]` — SSE event queues per run
- `_agent_sandboxes: dict[str, Sandbox]` — Live E2B sandbox handles
- `_pending_questions: dict[str, dict]` — Unanswered agent questions

`start_agent_run()` flow:
1. Creates E2B sandbox with configured template/timeout
2. Writes `/comms/mission.json` (repo URL, Gemini key, GitHub token, portfolio config)
3. Starts `python3 /agent/main.py` as background process
4. Enters `_monitor_agent()` polling loop (every 2s)

Monitor reads 3 files: `/comms/status.json`, `/comms/progress.json`, `/comms/question.json`

### IPC Protocol (file-based, via sandbox filesystem)

| Direction | File | Contents |
|---|---|---|
| Backend → Agent | `/comms/mission.json` | repo_url, gemini_api_key, github_token, portfolio config |
| Backend → Agent | `/comms/answer.json` | question_id, text |
| Agent → Backend | `/comms/status.json` | status: running/completed/failed, error |
| Agent → Backend | `/comms/progress.json` | stage, message, timestamp |
| Agent → Backend | `/comms/question.json` | question_id, text, options |
| Agent → Backend | `/output/result.json` | post_draft, images, exploration_log, portfolio_pr_url |
| Agent → Backend | `/output/images/*.png` | Downloaded README images |

### Database (PostgreSQL + SQLAlchemy Async)
4 tables: `users`, `runs`, `drafts`, `tokens`

Run statuses: `pending → agent_starting → agent_exploring → agent_generating → agent_awaiting_answer → agent_updating_portfolio → completed | failed`

### API Routes
- `/api/runs` — CRUD + agent launch + SSE stream + answer endpoint
- `/api/drafts` — Draft CRUD
- `/api/linkedin` — OAuth + publishing
- `/api/settings` — User preferences

## E2B Agent (e2b-agent/)

Standalone Python that runs inside E2B sandbox. Zero dependency on backend code.

### Pipeline Steps
1. `explore_repo()` — shallow clone, read README (up to 4000 chars), walk up to 500 files, read config files
2. `extract_images()` — regex scan README for markdown/HTML images, download up to 5
3. `generate_post()` — Gemini 2.0 Flash with structured JSON output
4. `update_portfolio()` — optional: clone portfolio repo, append entry, push branch, create PR

### Dependencies
- `google-genai` — Gemini 2.0 Flash (free tier)
- `httpx` — HTTP client for image downloads
- `git` — repo cloning

## Frontend (Next.js 14)

### Key Libraries
- NextAuth.js — GitHub OAuth
- SWR — data fetching
- EventSource — SSE for real-time agent progress

### Pages
- `/` — Landing
- `/dashboard` — Start new run
- `/runs/[id]` — Live agent progress + question answering
- `/runs/[id]/review` — Edit/publish post
- `/drafts` — Saved drafts
- `/history` — Published posts
- `/settings` — User preferences

### Key Types
- `AgentOutput` — post_draft, images, exploration_log, portfolio_pr_url
- `AgentQuestion` — question_id, text, options (for interactive agent questions)
- `SSEEvent` — stage, message, stream_url, question

## External Services
- **E2B** — Sandbox runtime (required)
- **Gemini 2.0 Flash** — LLM for post generation (required, free tier)
- **GitHub** — OAuth login + repo access
- **Cloudflare R2** — Image storage (optional)
- **LinkedIn** — OAuth + publishing (optional)

## Key Dependencies
Backend: fastapi, sqlalchemy[asyncio], asyncpg, e2b-desktop, google-genai, httpx, pillow, cryptography, boto3, sse-starlette
Frontend: next, react, next-auth, swr, tailwindcss
