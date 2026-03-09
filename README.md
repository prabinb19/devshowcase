# DevShowcase

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB.svg)](https://python.org)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/Tests-151_passing-brightgreen.svg)](#running-tests)

An AI agent app I built to learn how to secure self-hosted agent runtimes. I used three Microsoft security frameworks as checklists: the [OpenClaw threat analysis](https://www.microsoft.com/en-us/security/blog/2026/02/19/running-openclaw-safely-identity-isolation-runtime-risk/) (6 control domains), the [Security Development Lifecycle](https://www.microsoft.com/en-us/securityengineering/sdl/practices) (SDL), and the [Responsible AI Standard v2](https://www.microsoft.com/en-us/ai/principles-and-approach).

## Background

I have been learning to build with AI agents recently and it is genuinely fun. Vibe coding is fun. But after talking to my mentor, I realized there is so much about security I do not know. If we cannot build securely with AI agents and tools, are we even building anything worth shipping?

That got me thinking. I found [this Microsoft article](https://www.microsoft.com/en-us/security/blog/2026/02/19/running-openclaw-safely-identity-isolation-runtime-risk/) where Microsoft Defender's security research team analyzes the risks of OpenClaw, a third-party self-hosted agent runtime. Their main point is that OpenClaw is not safe to run. It can ingest untrusted text, download and execute code from external sources, and act using whatever credentials you give it. Microsoft recommends not running it at all, or if you must, only in a fully isolated environment with dedicated credentials.

The article is not a how-to guide. It is a threat analysis with hunting queries for Microsoft Defender XDR. But buried in there is a table that maps six security control domains (Identity, Endpoint & Host, Supply Chain, Network & Egress, Data Protection, Monitoring & Response) to concrete risks. I used those six domains as a starting point, then expanded into two more Microsoft frameworks — the SDL for secure coding practices and the Responsible AI Standard for AI-specific safety.

The app itself takes a GitHub repo URL, runs it through an AI pipeline (analyze the code, capture screenshots, generate a LinkedIn post), and lets you publish it. The interesting part was going back through my own code and finding all the security holes. There were a lot.

## Security Frameworks Applied

This project is hardened against three Microsoft security frameworks. Full implementation details are in [docs/security-hardening.md](docs/security-hardening.md).

### 1. Microsoft OpenClaw Threat Analysis — 6 Control Domains

The [Microsoft Defender team's threat analysis](https://www.microsoft.com/en-us/security/blog/2026/02/19/running-openclaw-safely-identity-isolation-runtime-risk/) identifies six control domains for securing self-hosted agent runtimes. I implemented fixes that cover all six.

| # | Fix | Domain | What was wrong |
|---|-----|--------|----------------|
| 1 | JWT Auth Middleware | Identity | I was using raw `X-GitHub-*` headers for auth. Anyone could spoof them. Replaced with signed JWTs (5-min TTL) |
| 2 | Ownership Validation | Identity + Data | Users could access each other's drafts and runs by guessing IDs. Added `user_id` checks on every endpoint |
| 3 | OAuth State Validation | Identity | LinkedIn OAuth had no CSRF protection. Added single-use, time-limited, user-bound state tokens |
| 4 | Prompt Injection Defense | Data Protection | Repo READMEs are untrusted input but I was feeding them straight to the LLM. Added an instruction hierarchy and input truncation |
| 5 | Sandbox Secrets Scoping | Endpoint & Host | The AI agent sandbox had access to all my env vars, including database credentials. Scoped it down to only 3 variables |
| 6 | SSRF Prevention | Network & Egress | The app fetches image URLs from repos. Without validation, it could hit cloud metadata endpoints or internal IPs. Added a blocklist + DNS resolution checks |
| 7 | Error Sanitization | Data Protection | Stack traces and SQL errors were leaking to the frontend. Now clients get generic messages, full details stay in server logs |
| 8 | Dependency Pinning | Supply Chain | Dependencies had no version constraints. Pinned everything to prevent malicious package injection |
| 9 | Structured Audit Logging | Monitoring | No way to tell if credentials were compromised. Added JSON audit logs for auth, publish, and token events |

### 2. Microsoft Security Development Lifecycle (SDL)

The [SDL](https://www.microsoft.com/en-us/securityengineering/sdl/practices) defines secure coding practices across requirements, design, implementation, verification, and release. The OpenClaw fixes cover a lot of SDL ground, but two areas had gaps: browser-side security headers and overly permissive CORS.

| # | Fix | SDL Phase | What changed |
|---|-----|-----------|--------------|
| 10 | Content-Security-Policy & Security Headers | Implementation | Added CSP with allowlisted sources, X-Frame-Options DENY, X-Content-Type-Options nosniff, strict Referrer-Policy, and Permissions-Policy disabling camera/mic/geo |
| 11 | CORS Hardening | Design | Replaced `allow_methods=["*"]` and `allow_headers=["*"]` with explicit allowlists: only the HTTP methods and headers the app actually uses |

### 3. Microsoft Responsible AI Standard v2

The [Responsible AI Standard](https://www.microsoft.com/en-us/ai/principles-and-approach) defines six principles: fairness, reliability & safety, privacy & security, inclusiveness, transparency, and accountability. Two gaps stood out — no content safety filtering on LLM output, and no disclosure that content is AI-generated.

| # | Fix | RAI Principle | What changed |
|---|-----|---------------|--------------|
| 12 | LLM Output Content Safety Filter | Reliability & Safety | Added a blocklist that catches violent language, hateful content, credential leaks, prompt injection echoes, role hijack echoes, and system prompt leaks before storing any AI-generated draft |
| 13 | AI Transparency Disclosure | Transparency | Added an "AI-Generated Content" banner on the review page with a link to Microsoft's Responsible AI principles. Also aligns with the [AI Code of Conduct](https://learn.microsoft.com/en-us/legal/ai-code-of-conduct) (no deceptive AI content) |

### Coverage Summary

| Domain | Fixes |
|--------|-------|
| **Identity** | JWT auth (#1), ownership checks (#2), OAuth state (#3) |
| **Endpoint & Host** | Sandbox secrets scoping (#5) |
| **Supply Chain** | Dependency pinning (#8) |
| **Network & Egress** | SSRF prevention (#6), CSP headers (#10), CORS hardening (#11) |
| **Data Protection** | Prompt injection defense (#4), error sanitization (#7), content safety filter (#12), AI disclosure (#13) |
| **Monitoring & Response** | Structured audit logging (#9) |

## How the App Works

You paste a GitHub repo URL and the app runs a 4-stage LangGraph pipeline:

1. **Ingest** - Fetches repo metadata, README, file tree, and config files from the GitHub API
2. **Analyze** - Claude looks at the repo and identifies the project type, tech stack, and highlights
3. **Capture** - Extracts images from the README or generates a branded project card
4. **Generate** - Writes a LinkedIn post with a hook, body, alt texts, and first comment

```
Next.js Frontend --> FastAPI Backend --> LangGraph Pipeline --> PostgreSQL
                                              |
                                         E2B Sandbox
                                      (AI agent runs here)
```

You can edit the draft, preview how it will look on LinkedIn, and publish directly through OAuth.

## Tech Stack

**Backend:** Python 3.12, FastAPI, LangGraph, SQLAlchemy, Anthropic SDK, httpx

**Frontend:** Next.js 14, TypeScript, Tailwind CSS, NextAuth.js, SWR

**Infrastructure:** PostgreSQL (Neon), Cloudflare R2, E2B (sandboxed execution), Railway, Vercel

## Local Development

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker (for local PostgreSQL)

### Setup

```bash
git clone https://github.com/prabinb19/devshowcase.git
cd devshowcase

# Start PostgreSQL
docker compose up -d

# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # fill in API keys
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (in another terminal)
cd frontend
npm install
cp .env.example .env.local  # fill in OAuth credentials
npm run dev
```

### Environment Variables

**Backend** (`.env`):

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `GITHUB_TOKEN` | GitHub personal access token |
| `TOKEN_ENCRYPTION_KEY` | Fernet key for encrypting OAuth tokens at rest |
| `NEXTAUTH_SECRET` | Shared secret for JWT verification with frontend |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` | Cloudflare R2 credentials |
| `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` | LinkedIn OAuth app credentials |

**Frontend** (`.env.local`):

| Variable | Description |
|----------|-------------|
| `NEXTAUTH_SECRET` | Secret for session encryption |
| `NEXTAUTH_URL` | App URL (http://localhost:3000 for local) |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | GitHub OAuth credentials |
| `NEXT_PUBLIC_API_URL` | Backend URL (http://localhost:8000 for local) |

## Running Tests

```bash
cd backend
.venv/bin/python -m pytest tests/ -v
```

151 tests covering pipeline nodes, API routes, security controls, and services. All mocked, no API keys needed.

Security-specific tests:

```bash
.venv/bin/python -m pytest tests/ -v -k "auth or forbidden or state or ssrf or audit or error or content_safety"
```

## Deployment

**Backend (Railway):** Connect repo, set root to `backend/`, add env vars, Railway detects the Dockerfile.

**Frontend (Vercel):** Import repo, set root to `frontend/`, add env vars, point `NEXT_PUBLIC_API_URL` to Railway.

## References

- [Microsoft: Running OpenClaw Safely](https://www.microsoft.com/en-us/security/blog/2026/02/19/running-openclaw-safely-identity-isolation-runtime-risk/) — the threat analysis I used as the initial security checklist (6 control domains)
- [Microsoft Security Development Lifecycle (SDL)](https://www.microsoft.com/en-us/securityengineering/sdl/practices) — secure coding practices across the development lifecycle
- [Microsoft Responsible AI Standard v2](https://www.microsoft.com/en-us/ai/principles-and-approach) — six principles for ethical AI (fairness, reliability, privacy, inclusiveness, transparency, accountability)
- [Microsoft AI Code of Conduct](https://learn.microsoft.com/en-us/legal/ai-code-of-conduct) — requirements for AI services, aligned with EU AI Act
- [Microsoft SDL for AI (Feb 2026)](https://www.microsoft.com/en-us/security/blog/2026/02/03/microsoft-sdl-evolving-security-practices-for-an-ai-powered-world/) — how Microsoft is evolving SDL for AI-specific threats

## License

[MIT License](LICENSE)
