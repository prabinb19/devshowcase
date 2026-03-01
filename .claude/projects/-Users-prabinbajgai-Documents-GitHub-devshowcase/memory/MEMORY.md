# DevShowcase Project Memory

## What This App Does
DevShowcase transforms GitHub repositories into polished LinkedIn posts using an autonomous AI agent. Pipeline: Create run → Agent starts in E2B sandbox → Clones repo → Analyzes code → Extracts README images → Generates LinkedIn post via Gemini Flash → Returns results.

## Workflow Preferences
- **Do NOT push automatically**: After committing, always ask the user before running `git push`.

## Environment
- **Always use `.venv/bin/python`** to run pytest and Python commands. System `python`/`python3` does not have project dependencies installed.
  - Correct: `.venv/bin/python -m pytest tests/ -v`
  - Wrong: `python -m pytest` or `python3 -m pytest`
- Backend root: `backend/`
- Frontend root: `frontend/`
- Python 3.12.12, pytest 9.0.2, pytest-asyncio with `mode=Mode.AUTO`
- Frontend: Next.js 14, React 18, TypeScript 5, Tailwind CSS

## Architecture Overview
- See `memory/architecture.md` for full details
- Backend: FastAPI (thin agent gateway) + E2B sandbox + PostgreSQL + Cloudflare R2
- Agent: Autonomous Python process in E2B sandbox using Gemini 2.0 Flash
- Frontend: Next.js 14 App Router + NextAuth (GitHub OAuth) + SWR
- 4 DB tables: users, runs, drafts, tokens
- 5 DB migrations in backend/alembic/versions/
- API endpoints across 4 routers (runs, drafts, linkedin, settings)
- Agent IPC: file-based communication via /comms/ and /output/ in sandbox
- Deploy: Railway (backend) + Vercel (frontend)

## Key Architecture Change (latest)
- **Old**: LangGraph 4-node pipeline (ingest→analyze→capture→generate) running Claude/Anthropic on backend
- **New**: Autonomous agent in E2B sandbox using Gemini 2.0 Flash. Backend is stateless gateway.
- Deleted: graph.py, state.py, nodes/, prompts/, services/screenshot/, llm_client.py, run_executor.py
- Added: services/agent_executor.py, e2b-agent/ directory
- Run statuses: pending → agent_starting → agent_exploring → agent_generating → agent_awaiting_answer → agent_updating_portfolio → completed | failed
- Two-way agent communication: agent can ask questions (question.json), user answers (answer.json)
- Agent output stored in `agent_output` JSON column on Run model

## E2B Agent Structure (e2b-agent/)
- main.py: orchestrates 4-step pipeline
- comms.py: file-based IPC helpers
- explorer.py: git clone, README, file tree, config files
- image_extractor.py: extract/download README images
- post_generator.py: Gemini Flash structured JSON generation
- portfolio_updater.py: optional portfolio repo PR
