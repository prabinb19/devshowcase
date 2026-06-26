# DevShowcase — Local Setup Guide

> Complete setup for the full application: GitHub repo analysis via an autonomous E2B sandbox agent (Gemini), LinkedIn post generation, OAuth login, and publishing.

## Prerequisites

- **Docker Desktop** — [download](https://www.docker.com/products/docker-desktop/)
- **Python 3.12+** — [download](https://www.python.org/downloads/)
- **Node.js 18+** — [download](https://nodejs.org/)
- **Git**

---

## Step 1: Clone & Start Services

```bash
git clone https://github.com/prabinb19/devshowcase.git
cd devshowcase
```

### Option A: Full Stack with Docker (recommended)

After configuring env files (Steps 2-3), run everything in one command:

```bash
make up
```

This starts PostgreSQL, backend, and frontend together. The backend and frontend containers mount your source code for hot-reloading.

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend: [http://localhost:8000](http://localhost:8000)
- PostgreSQL: `localhost:5432`

### Option B: PostgreSQL Only (manual setup)

If you prefer running backend and frontend outside Docker:

```bash
docker compose up -d postgres
```

This starts Postgres 16 on `localhost:5432` with:

- Database: `devshowcase`
- User: `postgres` / Password: `dev`

Verify it's running:

```bash
docker compose logs postgres
```

---

## Step 2: Get Your API Keys

### 2a. GitHub OAuth App (for login)

1. Go to [github.com/settings/applications/new](https://github.com/settings/applications/new)
2. Fill in:
  - **Application name**: `DevShowcase Local`
  - **Homepage URL**: `http://localhost:3000`
  - **Authorization callback URL**: `http://localhost:3000/api/auth/callback/github`
3. Click **Register application**
4. Copy the **Client ID**
5. Click **Generate a new client secret** — copy it immediately (shown only once)

### 2b. GitHub Personal Access Token (for repo cloning inside sandbox)

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens?type=beta)
2. Click **Generate new token (Fine-grained)**
3. Give it a name, set expiration
4. Under **Repository access**, select **Public Repositories (read-only)**
5. Click **Generate token** — copy it

### 2c. Gemini API Key (required — powers the E2B sandbox agent)

The autonomous agent that runs inside the E2B sandbox uses Gemini for repo analysis and structured post generation.

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Click **Create API Key**
3. Copy the key
4. Gemini 2.5 Flash is used (free tier available)

### 2d. E2B API Key (required — agent sandbox runtime)

The E2B sandbox hosts the autonomous agent that clones repos, explores code, extracts images, and generates posts via Gemini.

1. Go to [e2b.dev](https://e2b.dev) and sign up (free tier available)
2. Navigate to **Dashboard > API Keys**
3. Create a new API key — copy it (starts with `e2b_...`)

**How it works:**

The backend provisions an E2B sandbox and runs an autonomous agent inside it. The agent clones the repo, explores it with Gemini, identifies the project type and tech stack, extracts images from the README (or builds a project card), and drafts a LinkedIn post — writing results back to the backend. The backend streams progress to the frontend via SSE and stores the final draft.

**Quick smoke test** (after setting `E2B_API_KEY` in `.env`):

```bash
cd backend
.venv/bin/python -c "
from e2b_desktop import Sandbox
import os
from dotenv import load_dotenv
load_dotenv()
desktop = Sandbox.create(api_key=os.environ['E2B_API_KEY'], resolution=(1280, 800), timeout=60)
print('Sandbox created successfully')
desktop.kill()
print('Sandbox killed — E2B is working!')
"
```

### Custom E2B Agent Template (recommended)

Build the custom agent template for pre-installed dependencies:

1. Install the E2B CLI: `npm install -g @e2b/cli`
2. Authenticate: `e2b auth login`
3. Build the agent template:
   ```bash
   cd e2b-agent/
   e2b template create devshowcase-agent --dockerfile Dockerfile
   ```
4. Set `E2B_TEMPLATE_ID=devshowcase-desktop-agent` in your `.env`

Without a custom template, the default E2B template is used (may be slower as it installs dependencies at runtime).

### 2e. Cloudflare R2 (optional — for image storage)

> **You can skip this for local dev.** Images extracted from README files are stored in the sandbox and returned in the agent output. R2 is used for persistent cloud storage.

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) → **R2 Object Storage**
2. Click **Create Bucket** → name it `devshowcase-local`
3. Note your **Account ID** from the URL or sidebar
4. Go to **Manage R2 API Tokens** → **Create API Token**
5. Set permissions to **Object Read & Write**, scope to your bucket
6. Copy the **Access Key ID** and **Secret Access Key**

### 2f. LinkedIn OAuth (optional — for publishing)

> **Skip this unless you want to publish posts to LinkedIn.** The app works fully without it — you can generate, review, edit, and save drafts.

1. Go to [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps) and create an app
2. Request the **Share on LinkedIn** product
3. Under **Auth**, note the **Client ID** and **Client Secret**
4. Add redirect URL: `http://localhost:3000/api/linkedin/callback`

---

## Step 3: Configure Environment Files

### Backend (`backend/.env`)

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`:

```env
# Database (matches docker-compose.yml defaults)
DATABASE_URL=postgresql+asyncpg://postgres:dev@localhost:5432/devshowcase

# Gemini (required — powers the AI agent inside the E2B sandbox)
GEMINI_API_KEY=your-gemini-api-key

# GitHub (required — personal access token for repo cloning)
GITHUB_TOKEN=github_pat_your-token-here

# E2B (required — sandbox runtime for the agent)
E2B_API_KEY=e2b_your-key-here

# E2B template (optional — custom agent template)
E2B_TEMPLATE_ID=devshowcase-desktop-agent

# Enable live desktop stream for agent sandbox (default: true)
# E2B_ENABLE_STREAM=true

# Agent sandbox timeout in seconds (default: 600)
# AGENT_SANDBOX_TIMEOUT=600

# Token encryption (required — generate with command below)
TOKEN_ENCRYPTION_KEY=

# Portfolio PR feature (optional)
# PORTFOLIO_REPO=
# PORTFOLIO_OWNER=

# Cloudflare R2 (optional — skip for local dev)
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=

# LinkedIn OAuth (optional — skip if not publishing)
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
```

Generate an encryption key:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Frontend (`frontend/.env.local`)

```bash
cp frontend/.env.example frontend/.env.local
```

Edit `frontend/.env.local`:

```env
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=<generate with: openssl rand -base64 32>
GITHUB_CLIENT_ID=your-github-oauth-client-id
GITHUB_CLIENT_SECRET=your-github-oauth-client-secret
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Generate the NextAuth secret:

```bash
openssl rand -base64 32
```

---

## Step 4: Set Up & Run

### If using Docker (Option A from Step 1):

```bash
# Start everything
make up
```

That's it. The backend runs migrations automatically on startup. Skip to Step 6.

### If running manually (Option B from Step 1):

**Backend:**

```bash
cd backend

# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start the backend server (from repo root)
cd ..
make dev-backend
```

Verify: open [http://localhost:8000/health](http://localhost:8000/health) — should return `{"status": "ok"}`

**Frontend** (in a new terminal):

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server (from repo root)
cd ..
make dev-frontend
```

Verify: open [http://localhost:3000](http://localhost:3000)

### Available Make Commands

| Command | Description |
|---------|-------------|
| `make up` | Start full stack with Docker |
| `make down` | Stop all containers |
| `make dev-backend` | Run backend locally (requires .venv) |
| `make dev-frontend` | Run frontend locally (requires node_modules) |
| `make db-migrate` | Run Alembic migrations |
| `make test` | Run backend tests |
| `make lint` | Run ruff + eslint |

---

## Step 6: Test the Full Flow

1. Open [http://localhost:3000](http://localhost:3000)
2. Click **Sign in with GitHub**
3. Authorize the OAuth app
4. On the dashboard, paste a **public GitHub repo URL** (e.g. `https://github.com/fastapi/fastapi`)
5. Watch the agent progress in real-time (ingesting → analyzing → generating → capturing → completed)
6. If the agent needs clarification, it will ask a question — answer it in the UI
7. Review the generated LinkedIn post draft
8. Edit the post body, first comment, select/deselect images, update alt texts
9. Choose an action:
   - **Save as Draft** — saves to the drafts page for later
   - **Publish to LinkedIn** — requires LinkedIn OAuth setup (Step 2f)
10. Visit **Settings** to configure default tone and hashtag preferences
11. Visit **History** to see previously published posts

---

## Running Tests

```bash
cd backend
make test
```

Tests use mocks — no real API keys needed.

---

## Application Pages

| Page | URL | Description |
| --- | --- | --- |
| Landing | `/` | Hero, how-it-works, sign-in |
| Dashboard | `/dashboard` | Paste GitHub URL to start a run |
| Run Status | `/runs/[id]` | Live agent progress via SSE |
| Review | `/runs/[id]/review` | Edit post, preview, publish/save |
| Drafts | `/drafts` | Saved draft posts |
| History | `/history` | Published LinkedIn posts |
| Settings | `/settings` | Tone, hashtags, LinkedIn connection |

---

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/health` | Health check |
| `POST` | `/api/runs` | Start a new agent run |
| `GET` | `/api/runs/{id}` | Get run status and results (includes `agent_output`) |
| `GET` | `/api/runs/{id}/stream` | SSE stream for live agent progress |
| `POST` | `/api/runs/{id}/answer` | Submit answer to agent question |
| `POST` | `/api/drafts` | Create a draft |
| `GET` | `/api/drafts` | List drafts (optional `?status=` filter) |
| `GET` | `/api/drafts/{id}` | Get a single draft |
| `PATCH` | `/api/drafts/{id}` | Update a draft |
| `DELETE` | `/api/drafts/{id}` | Delete a draft |
| `GET` | `/api/settings` | Get user preferences |
| `PUT` | `/api/settings` | Update user preferences |
| `GET` | `/api/linkedin/auth-url` | Get LinkedIn OAuth URL |
| `POST` | `/api/linkedin/callback` | Exchange OAuth code for tokens |
| `GET` | `/api/linkedin/status` | Check LinkedIn connection |
| `POST` | `/api/linkedin/publish` | Publish a draft to LinkedIn |
| `DELETE` | `/api/linkedin/disconnect` | Disconnect LinkedIn account |

---

## Quick Reference

| Service | URL |
| --- | --- |
| Frontend | [http://localhost:3000](http://localhost:3000) |
| Backend API | [http://localhost:8000](http://localhost:8000) |
| Health Check | [http://localhost:8000/health](http://localhost:8000/health) |
| PostgreSQL | localhost:5432 |

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `JWEDecryptionFailed` on login | Clear browser cookies for localhost, restart frontend |
| `connection refused` on port 5432 | Run `docker compose up -d postgres` and wait a few seconds |
| Docker build fails | Run `docker compose down` then `make up` to rebuild from scratch |
| `ModuleNotFoundError` | Make sure you're using `.venv/bin/python`, not system Python |
| CORS errors in browser | Ensure backend is running on port 8000, frontend on 3000 |
| GitHub OAuth callback error | Verify callback URL is exactly `http://localhost:3000/api/auth/callback/github` |
| LinkedIn OAuth callback error | Verify redirect URL is `http://localhost:3000/api/linkedin/callback` in LinkedIn app settings |
| Agent stuck or timed out | Check E2B API key is valid, increase `AGENT_SANDBOX_TIMEOUT` if needed |
| Sandbox fails to create | Verify `E2B_API_KEY` is set, or run the smoke test in Step 2d |
| Agent question never appears | Check SSE connection — frontend must be connected to `/api/runs/{id}/stream` |
| `422` on settings save | Check that tone is one of: professional, casual, technical, enthusiastic |
| Tests fail with `ModuleNotFoundError` | Run tests with `.venv/bin/python -m pytest tests/ -v`, not `pytest` directly |

---

## What's Required vs Optional

| Key | Required? | Impact if missing |
| --- | --- | --- |
| `DATABASE_URL` | **Yes** | Nothing works |
| `GEMINI_API_KEY` | **Yes** | E2B sandbox agent can't analyze repos or generate posts |
| `GITHUB_TOKEN` | **Yes** | Agent can't clone repos |
| `E2B_API_KEY` | **Yes** | Agent sandbox can't start |
| `GITHUB_CLIENT_ID/SECRET` | **Yes** | Can't log in |
| `NEXTAUTH_SECRET` | **Yes** | Auth won't work |
| `TOKEN_ENCRYPTION_KEY` | **Yes** | Required for token storage (LinkedIn, future integrations) |
| `E2B_TEMPLATE_ID` | No | Falls back to default E2B template (slower) |
| `E2B_ENABLE_STREAM` | No | Defaults to `true` (live desktop stream) |
| `PORTFOLIO_REPO/OWNER` | No | Portfolio PR feature disabled |
| `R2_*` keys | No | Images won't persist to cloud storage |
| `LINKEDIN_CLIENT_ID/SECRET` | No | Can't publish to LinkedIn (draft save/edit still works) |

---

## Project Structure

```
devshowcase/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Pydantic settings
│   │   ├── database.py          # SQLAlchemy async engine
│   │   ├── middleware/           # Rate limiting
│   │   ├── models/              # SQLAlchemy models (User, Run, Draft, Token)
│   │   ├── routes/              # API routes (runs, drafts, settings, linkedin, images)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   └── services/            # Agent executor (E2B), R2, LinkedIn, image processing, encryption
│   ├── alembic/                 # Database migrations (5 versions)
│   ├── tests/                   # Unit tests
│   ├── Dockerfile               # Production Docker image
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js pages (landing, dashboard, runs, review, drafts, history, settings)
│   │   ├── components/          # UI components (navbar, button, input, card)
│   │   ├── lib/                 # API client, auth, hooks
│   │   └── types/               # TypeScript interfaces
│   └── package.json
├── e2b-agent/                   # Autonomous agent (runs inside E2B sandbox)
│   ├── Dockerfile               # ubuntu:22.04 + python3 + google-genai + git
│   ├── e2b.toml                 # Template: devshowcase-agent
│   └── agent/
│       ├── main.py              # Agent entry point: orchestrates the pipeline
│       ├── comms.py             # File-based IPC (mission, progress, status, questions)
│       ├── explorer.py          # Git clone + README + file tree + config analysis
│       ├── image_extractor.py   # Extract and download README images
│       ├── post_generator.py    # Gemini 2.5 Flash structured JSON generation
│       └── portfolio_updater.py # Optional: clone portfolio repo, push branch, create PR
├── e2b/                         # Legacy E2B desktop template (screenshot sandbox)
│   ├── Dockerfile               # Desktop template with Node.js 20, Python 3.12
│   └── e2b.toml                 # Template: devshowcase-desktop
├── docs/                        # Documentation
│   └── local-setup.md           # This file
├── docker-compose.yml           # Full stack: Postgres + backend + frontend
├── Makefile                     # Root commands: up, down, dev-backend, dev-frontend, test, lint
└── CLAUDE.md                    # Development guidelines
```
