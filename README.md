# DevShowcase

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB.svg)](https://python.org)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)

Turn GitHub repos into LinkedIn posts with AI.

DevShowcase takes a public GitHub repository URL, analyzes the codebase using Claude, captures screenshots, and generates a polished LinkedIn post — ready to edit and publish.

## Architecture

```
┌──────────────┐     ┌──────────────────────────────────────────┐
│   Next.js    │     │              FastAPI Backend              │
│   Frontend   │────▶│                                          │
│  (Vercel)    │     │  LangGraph Pipeline:                     │
└──────────────┘     │  Ingest → Analyze → Capture → Generate  │
                     │                                          │
                     │  Services:                               │
                     │  • GitHub API client                     │
                     │  • Claude (Anthropic) LLM                │
                     │  • Cloudflare R2 (screenshots)           │
                     │  • LinkedIn API (OAuth + publishing)     │
                     └──────────┬───────────────────────────────┘
                                │
                     ┌──────────▼───────────┐
                     │   PostgreSQL (Neon)   │
                     │  Users, Runs, Drafts  │
                     │  Tokens, Checkpoints  │
                     └──────────────────────┘
```

### Pipeline Stages

1. **Ingest** — Fetches repo metadata, README, file tree, and config files via the GitHub API. SSRF-protected.
2. **Analyze** — Claude identifies project type, tech stack, highlights, and screenshot strategy. Secrets are redacted before LLM processing.
3. **Capture** — Extracts README images or generates a branded project card (1200x630). Images are processed and uploaded to Cloudflare R2.
4. **Generate** — Crafts a LinkedIn-optimized post with hook, body, alt texts, and first comment.

## Features

- **One-click post generation** — Paste a GitHub URL, get a LinkedIn-ready post in seconds
- **AI-powered analysis** — Claude identifies project highlights, tech stack, and key features
- **Smart screenshots** — Extracts README images or generates branded project cards
- **Live pipeline tracking** — Real-time SSE progress updates as each stage completes
- **Full post editor** — Edit body, first comment, select screenshots, update alt texts
- **LinkedIn preview** — See exactly how your post will look before publishing
- **Direct publishing** — OAuth-connected LinkedIn publishing with auto-first-comment
- **Draft management** — Save, edit, and manage drafts before publishing
- **User preferences** — Configure default tone (professional/casual/technical/enthusiastic) and hashtags
- **Regeneration** — Provide feedback and regenerate posts without starting over

## Tech Stack

**Backend:** Python 3.12, FastAPI, LangGraph, SQLAlchemy (async), Anthropic SDK, httpx, Pillow, Fernet encryption

**Frontend:** Next.js 14 (App Router), TypeScript, Tailwind CSS, NextAuth.js, SWR

**Infrastructure:** PostgreSQL (Neon), Cloudflare R2, Railway (backend), Vercel (frontend)

## Local Development

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker (for local PostgreSQL)

### 1. Clone and Set Up

```bash
git clone https://github.com/prabinb19/devshowcase.git
cd devshowcase
```

### 2. Start PostgreSQL

```bash
docker compose up -d
```

### 3. Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Fill in API keys in .env
alembic upgrade head
uvicorn app.main:app --reload
```

### 4. Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env.local
# Fill in OAuth credentials in .env.local
npm run dev
```

### 5. Environment Variables

**Backend** (`.env`):

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg) |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude (required) |
| `ANTHROPIC_MODEL` | Claude model ID (default: `claude-sonnet-4-20250514`) |
| `CHECKPOINT_URL` | PostgreSQL psycopg3 URL for LangGraph checkpointer (optional) |
| `GITHUB_TOKEN` | GitHub personal access token (public repo access) |
| `TOKEN_ENCRYPTION_KEY` | Fernet key for encrypting OAuth tokens |
| `R2_ACCOUNT_ID` | Cloudflare R2 account ID |
| `R2_ACCESS_KEY_ID` | R2 access key |
| `R2_SECRET_ACCESS_KEY` | R2 secret key |
| `R2_BUCKET_NAME` | R2 bucket name |
| `LINKEDIN_CLIENT_ID` | LinkedIn OAuth app client ID |
| `LINKEDIN_CLIENT_SECRET` | LinkedIn OAuth app client secret |

**Frontend** (`.env.local`):

| Variable | Description |
|----------|-------------|
| `NEXTAUTH_SECRET` | Random secret for NextAuth.js session encryption |
| `NEXTAUTH_URL` | App URL (http://localhost:3000 for local dev) |
| `GITHUB_CLIENT_ID` | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth app client secret |
| `NEXT_PUBLIC_API_URL` | Backend URL (http://localhost:8000 for local dev) |

## Running Tests

```bash
cd backend
.venv/bin/python -m pytest tests/ -v
```

122 tests cover all pipeline nodes, API routes, and services — all use mocks, no API keys needed.

For a detailed setup walkthrough with key generation steps, see [`tasks/local-setup.md`](tasks/local-setup.md).

## Deployment

### Backend (Railway)

1. Connect the repository to Railway
2. Set the root directory to `backend/`
3. Railway will detect the Dockerfile automatically
4. Add all backend environment variables
5. Set `DATABASE_URL` to your Neon PostgreSQL connection string

### Frontend (Vercel)

1. Import the repository on Vercel
2. Set the root directory to `frontend/`
3. Add all frontend environment variables
4. Set `NEXT_PUBLIC_API_URL` to your Railway backend URL

## Project Structure

```
devshowcase/
├── backend/
│   ├── app/
│   │   ├── models/          # SQLAlchemy models (User, Run, Draft, Token)
│   │   ├── nodes/           # LangGraph pipeline nodes
│   │   ├── prompts/         # LLM system prompts
│   │   ├── routes/          # FastAPI route handlers
│   │   ├── schemas/         # Pydantic request/response models
│   │   ├── services/        # External service clients
│   │   ├── config.py        # Settings (env vars)
│   │   ├── database.py      # SQLAlchemy engine + session
│   │   ├── graph.py         # LangGraph pipeline definition
│   │   ├── main.py          # FastAPI app entry point
│   │   └── state.py         # LangGraph state + Pydantic data models
│   ├── alembic/             # Database migrations
│   ├── tests/               # pytest test suite
│   ├── Dockerfile           # Production container
│   └── pyproject.toml       # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js pages (App Router)
│   │   ├── components/      # Shared UI components
│   │   ├── lib/             # API client, hooks, auth config
│   │   └── types/           # TypeScript interfaces
│   ├── package.json
│   └── next.config.mjs
├── docker-compose.yml       # Local PostgreSQL
└── CLAUDE.md                # AI assistant instructions
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the [MIT License](LICENSE).
