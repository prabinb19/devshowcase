# DevShowcase — Local Setup Guide

> Complete setup for the full application: GitHub repo analysis pipeline, LinkedIn post generation, OAuth login, and publishing.

## Prerequisites

- **Docker Desktop** — [download](https://www.docker.com/products/docker-desktop/)
- **Python 3.12+** — [download](https://www.python.org/downloads/)
- **Node.js 18+** — [download](https://nodejs.org/)
- **Git**

---

## Step 1: Clone & Start PostgreSQL

```bash
git clone https://github.com/prabinb19/devshowcase.git
cd devshowcase
docker compose up -d
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

### 2b. GitHub Personal Access Token (for repo ingestion)

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens?type=beta)
2. Click **Generate new token (Fine-grained)**
3. Give it a name, set expiration
4. Under **Repository access**, select **Public Repositories (read-only)**
5. Click **Generate token** — copy it

### 2c. Anthropic API Key

1. Go to [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)
2. Click **Create Key**, name it `devshowcase-local`
3. Copy the key (starts with `sk-ant-...`)
4. Ensure you have billing set up under **Settings > Billing** (pay-as-you-go, ~$0.05/run)

### 2d. Cloudflare R2 (optional — for screenshot storage)

> **You can skip this for local dev.** The pipeline will still generate posts — screenshots just won't persist to cloud storage. Project card screenshots are generated locally via Pillow.

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) → **R2 Object Storage**
2. Click **Create Bucket** → name it `devshowcase-local`
3. Note your **Account ID** from the URL or sidebar
4. Go to **Manage R2 API Tokens** → **Create API Token**
5. Set permissions to **Object Read & Write**, scope to your bucket
6. Copy the **Access Key ID** and **Secret Access Key**

### 2e. LinkedIn OAuth (optional — for publishing)

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
CHECKPOINT_URL=postgresql://postgres:dev@localhost:5432/devshowcase

# Anthropic (required)
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# GitHub (required — personal access token for repo fetching)
GITHUB_TOKEN=github_pat_your-token-here

# Token encryption (required — generate with command below)
TOKEN_ENCRYPTION_KEY=

# E2B (optional — sandbox screenshots, can skip)
E2B_API_KEY=

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

## Step 4: Set Up the Backend

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

# Start the backend server
uvicorn app.main:app --reload --port 8000
```

Verify: open [http://localhost:8000/health](http://localhost:8000/health) — should return `{"status": "ok"}`

---

## Step 5: Set Up the Frontend

In a **new terminal**:

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

Verify: open [http://localhost:3000](http://localhost:3000)

---

## Step 6: Test the Full Flow

1. Open [http://localhost:3000](http://localhost:3000)
2. Click **Sign in with GitHub**
3. Authorize the OAuth app
4. On the dashboard, paste a **public GitHub repo URL** (e.g. `https://github.com/fastapi/fastapi`)
5. Watch the pipeline steps complete in real-time (ingest → analyze → capture → generate)
6. Review the generated LinkedIn post draft
7. Edit the post body, first comment, select/deselect screenshots, update alt texts
8. Choose an action:
   - **Save as Draft** — saves to the drafts page for later
   - **Publish to LinkedIn** — requires LinkedIn OAuth setup (Step 2e)
   - **Regenerate with Feedback** — provide feedback, re-runs the generate step
9. Visit **Settings** to configure default tone and hashtag preferences
10. Visit **History** to see previously published posts

---

## Running Tests

```bash
cd backend
.venv/bin/python -m pytest tests/ -v
```

All 122 tests should pass (they use mocks, no real API keys needed).

---

## Application Pages

| Page | URL | Description |
| --- | --- | --- |
| Landing | `/` | Hero, how-it-works, sign-in |
| Dashboard | `/dashboard` | Paste GitHub URL to start a run |
| Run Status | `/runs/[id]` | Live pipeline progress via SSE |
| Review | `/runs/[id]/review` | Edit post, preview, publish/save |
| Drafts | `/drafts` | Saved draft posts |
| History | `/history` | Published LinkedIn posts |
| Settings | `/settings` | Tone, hashtags, LinkedIn connection |

---

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/health` | Health check |
| `POST` | `/api/runs` | Start a new pipeline run |
| `GET` | `/api/runs/{id}` | Get run status and results |
| `GET` | `/api/runs/{id}/stream` | SSE stream for live progress |
| `POST` | `/api/runs/{id}/regenerate` | Regenerate with feedback |
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
| `connection refused` on port 5432 | Run `docker compose up -d` and wait a few seconds |
| `ModuleNotFoundError` | Make sure you're using `.venv/bin/python`, not system Python |
| CORS errors in browser | Ensure backend is running on port 8000, frontend on 3000 |
| GitHub OAuth callback error | Verify callback URL is exactly `http://localhost:3000/api/auth/callback/github` |
| LinkedIn OAuth callback error | Verify redirect URL is `http://localhost:3000/api/linkedin/callback` in LinkedIn app settings |
| Pipeline stuck on "capturing" | R2 credentials may be missing — screenshots fall back to project card if unconfigured |
| `422` on settings save | Check that tone is one of: professional, casual, technical, enthusiastic |
| Tests fail with `ModuleNotFoundError` | Run tests with `.venv/bin/python -m pytest tests/ -v`, not `pytest` directly |

---

## What's Required vs Optional

| Key | Required? | Impact if missing |
| --- | --- | --- |
| `DATABASE_URL` | **Yes** | Nothing works |
| `CHECKPOINT_URL` | **Yes** | LangGraph state persistence fails |
| `ANTHROPIC_API_KEY` | **Yes** | Pipeline can't analyze repos or generate posts |
| `GITHUB_TOKEN` | **Yes** | Pipeline can't fetch repo data |
| `GITHUB_CLIENT_ID/SECRET` | **Yes** | Can't log in |
| `NEXTAUTH_SECRET` | **Yes** | Auth won't work |
| `TOKEN_ENCRYPTION_KEY` | **Yes** | Required for token storage (LinkedIn, future integrations) |
| `R2_*` keys | No | Screenshots won't persist to cloud (project card still works locally) |
| `E2B_API_KEY` | No | Falls back to project card screenshots |
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
│   │   ├── graph.py             # LangGraph pipeline definition
│   │   ├── state.py             # AgentState + Pydantic models
│   │   ├── models/              # SQLAlchemy models (User, Run, Draft, Token)
│   │   ├── nodes/               # Pipeline nodes (ingest, analyze, capture, generate)
│   │   ├── routes/              # API routes (runs, drafts, settings, linkedin)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── services/            # Business logic (github, llm, r2, linkedin, screenshots)
│   │   └── prompts/             # LLM system prompts
│   ├── alembic/                 # Database migrations
│   ├── tests/                   # 122 unit tests
│   ├── Dockerfile               # Production Docker image
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js pages (landing, dashboard, runs, review, drafts, history, settings)
│   │   ├── components/          # UI components (navbar, button, input, card)
│   │   ├── lib/                 # API client, auth, hooks
│   │   └── types/               # TypeScript interfaces
│   └── package.json
├── docker-compose.yml           # Local Postgres
└── CLAUDE.md                    # Development guidelines
```
