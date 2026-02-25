# DevShowcase — Research Report & Refined Plan

## Context

This report evaluates the high-level-plan.md for DevShowcase — a web app where developers paste a GitHub URL and get AI-generated, platform-optimized social media posts with screenshots, ready to publish. Three parallel research agents investigated every stage. Below are findings, critical issues, and recommended refinements.

---

## CRITICAL ISSUES FOUND (Must Address Before Building)

### 1. Twitter/X Free Tier Cannot Upload Images
**Severity: HIGH** — The free tier ($0) does NOT include media upload endpoints. You need the **Basic tier ($100/month)** to attach images to tweets. This is the single largest fixed cost and fundamentally changes the Twitter value proposition.

**Recommendation:** Either:
- (A) Make Twitter text-only on free tier + offer "copy to clipboard" for manual posting with images
- (B) Add **Bluesky as a first-class platform** — free API, supports images, large dev community, open AT Protocol, mature Python SDK (`atproto`). Replace Twitter or make it optional
- (C) Budget $100/mo for Twitter Basic

### 2. SSRF Risk via GitHub URL Input
**Severity: HIGH** — Users submit URLs the backend fetches. A malicious user could submit internal/private network URLs. Must strictly validate to `https://github.com/{owner}/{repo}` format. Better: use GitHub API exclusively (never `git clone` on backend). If cloning is needed, clone ONLY inside E2B sandbox.

### 3. Prompt Injection via Malicious READMEs
**Severity: MEDIUM-HIGH** — A crafted README could manipulate the LLM into generating harmful/misleading posts. Mitigate with: separate extraction/generation LLM calls, system prompt hardening, content moderation pass, README truncation (8K tokens max), and the mandatory HITL review catches the rest.

### 4. LinkedIn Suppresses Posts with External Links
**Severity: MEDIUM** — LinkedIn's algorithm reduces reach for posts containing external URLs in the body. The GitHub link should go in a **first comment** (auto-posted immediately after the main post), not in the post body itself. This requires an extra API call but significantly improves reach.

### 5. Twitter's Aggressive Token Expiry
**Severity: MEDIUM** — Access tokens expire in **2 hours**. Refresh tokens rotate on each use (new refresh token issued, old one invalidated). If you fail to persist the new refresh token immediately, the user permanently loses access and must re-authenticate. Needs bulletproof refresh logic with atomic DB writes.

---

## STAGE-BY-STAGE EVALUATION

### Stage 1: INGEST (GitHub API) — SOLID, Minor Tweaks

**Verdict: Well-designed, low risk.**

| Aspect | Assessment |
|--------|-----------|
| Safety | Good. Fine-grained PAT with minimal scope. Add strict URL validation (SSRF). |
| Scalability | 5,000 req/hr with auth, ~5-10 calls per ingest. No concern. |
| Cost | Free (GitHub API). |
| Building | Straightforward. httpx + GitHub REST API. |

**Refinements:**
- Validate GitHub URLs server-side with regex: `^https://github\.com/[\w.-]+/[\w.-]+/?$`
- Never `git clone` on the backend host — only via GitHub API or inside E2B sandbox
- Drop "local folder path" from MVP — adds complexity, web app users won't have local access anyway
- Use `remark` + AST parsing for README image extraction (more reliable than regex)

---

### Stage 2: ANALYZE (Claude LLM) — SOLID

**Verdict: Good design. Claude Sonnet is the right model.**

| Aspect | Assessment |
|--------|-----------|
| Safety | Low risk. Read-only analysis. Add prompt injection defenses for README content. |
| Scalability | Single API call per run, ~8-12K tokens. No concern. |
| Cost | ~$0.02-0.03 per analysis call. |
| Building | Clean. Use Anthropic SDK directly (skip LangChain abstractions). |

**Refinements:**
- Call Anthropic API directly with `anthropic` Python SDK, not through LangChain — simpler, fewer dependencies, better error handling
- Use `tool_use` for structured output (already planned) — this is the most reliable way to get typed responses
- Add a content moderation check: ensure the analysis doesn't include secrets/API keys found in config files
- Truncate README to 8K tokens, file tree to 500 entries (already planned — good)

---

### Stage 3: CAPTURE (E2B Sandbox + Screenshots) — HIGHEST RISK STAGE

**Verdict: E2B is the right choice for MVP, but expect ~40-60% success rate on arbitrary repos.**

| Aspect | Assessment |
|--------|-----------|
| Safety | Firecracker microVMs — same isolation as AWS Lambda. No documented escapes. Solid. |
| Scalability | E2B Hobby = ~100 sandbox-hours/mo free. At 3 min/run, that's ~2000 runs. Good for MVP. |
| Cost | ~$0.02-0.03 per run (2-3 min). At 1000 runs/mo with 4vCPU: $100-200/mo. |
| Building | **Hardest stage.** Playwright in sandboxes is finicky. Needs iterative tuning. |

**Critical findings:**
1. **Don't use Playwright's `networkidle`** for dev servers — HMR WebSocket connections never close, causing hangs. Use `domcontentloaded` + fixed 2-3s wait instead
2. **Prefer production builds** (`npm run build && npm run preview/start`) over dev servers — cleaner output, no HMR overlays, more reliable
3. **Pre-build a custom E2B template** with Node 20, Python 3.12, Playwright + Chromium pre-installed. This cuts cold start and install time dramatically
4. **Framework detection heuristics** are essential — check `package.json` for known frameworks (React/Next.js/Vue/Vite/Svelte) and map to correct build/serve commands
5. **Multiple screenshots at intervals** — take 3 screenshots at 1s, 3s, 5s after load, pick best (largest file = most content rendered)
6. **Sandbox timeouts**: 5-minute hard limit per sandbox, 180s for the entire capture stage

**For project card generation (fallback):** Use **Satori/@vercel/og** (50-200ms, no browser needed, JSX-to-SVG-to-PNG). Design at 1200x630px. Include: repo name, description, stars, primary language, tech stack icons.

**Recommended initial scope:** Support only Node.js web frameworks (React, Next.js, Vue, Vite, Svelte) for sandbox screenshots. Everything else falls back to README images or project cards. Expand framework support over time.

---

### Stage 4: GENERATE (Post Drafts) — SOLID, Good Refinements Available

**Verdict: Well-designed. A few platform-specific optimizations.**

| Aspect | Assessment |
|--------|-----------|
| Safety | Low risk. HITL catches hallucinations. Ground strictly on README. |
| Scalability | 2-3 LLM calls, ~5-8K tokens each. No concern. |
| Cost | ~$0.03-0.05 per run (all calls combined). |
| Building | Moderate. Prompt engineering is iterative. Few-shot examples are key. |

**Refinements (LinkedIn-only MVP):**
- **Don't put GitHub link in post body** (algorithmic suppression). Generate the post text without links, then auto-post the link as a first comment via API
- First ~210 chars are visible before "see more" fold — the hook MUST be in those chars
- **Alt text generation** is a great accessibility feature — keep it
- **Image size:** 1200x627px for LinkedIn. Generate at 2x (2400x1254) for retina, compress JPEG at quality 85%, target under 1MB
- MVP generates only LinkedIn posts. Twitter/Bluesky generation nodes added in later phases
- Only 2 LLM calls needed for MVP: (1) project analysis, (2) LinkedIn post. Cuts cost per run

---

### Stage 5: REVIEW (Human-in-the-Loop UI) — SOLID

**Verdict: Well-designed. The mandatory HITL is the right call.**

No major concerns. The UI mockup is comprehensive. Minor additions:
- Add character count warnings (yellow at 90%, red at limit)
- Show a "post preview" that mimics how it'll look on each platform
- Add a "LinkedIn comment" field for the auto-posted first comment containing the GitHub link

---

### Stage 6: PUBLISH (Social APIs) — LinkedIn Only for MVP

**Verdict: LinkedIn flow is solid. Other platforms deferred.**

| Platform | MVP? | Status |
|----------|------|--------|
| LinkedIn | YES | Apply for "Share on LinkedIn" product ASAP (can take days-weeks). Image upload is 2-step. Implement first-comment for GitHub link. |
| Bluesky | Phase 2 | Free API, image support, `atproto` Python SDK. Easy to add after MVP. |
| Twitter/X | Phase 3 | Free tier = no images. Basic = $100/mo. 2-hour token expiry. Defer until needed. |

**LinkedIn OAuth details:** `w_member_social` scope. Access tokens: 60 days. Refresh tokens: 365 days. Rate limit: 150 posts/day per member.

**Twitter refresh token gotcha:** Each refresh issues a NEW refresh token and invalidates the old one. Must persist atomically (DB transaction) before any other operation.

---

## ARCHITECTURE REFINEMENTS

### Database: Skip SQLite, Start with Postgres
- LangGraph's `SqliteSaver` is explicitly **development-only**. `PostgresSaver` is production-ready.
- **Neon Postgres** (free tier: 0.5GB forever, auto-suspend when idle) or Railway's built-in Postgres
- Avoids the SQLite→Postgres migration pain (datetime types, concurrency, enums)

### Image Storage: Cloudflare R2 over Supabase Storage
- **Zero egress fees** — screenshots shared on social media generate many image loads from viewers
- 10GB free storage, S3-compatible API (use `boto3`)
- Automatic global CDN

### Hosting: Railway over Fly.io
- Better DX for solo developer (one-click Postgres, simple CLI, built-in env management)
- Hobby tier: $5/mo with usage-based billing
- Supports long-lived SSE connections

### SSE: Connect Frontend Directly to Backend
- Frontend SSE must connect **directly** to the FastAPI backend (not through Vercel API routes, which timeout at 30s)
- Set CORS headers on FastAPI to allow Vercel frontend origin
- Send heartbeat `:keepalive\n\n` every 15-20 seconds to prevent proxy timeouts

### LangGraph: Keep It, But Stay Lean
- The HITL interrupt/resume pattern justifies LangGraph over plain async Python
- Use `PostgresSaver` from day 1 (not SqliteSaver)
- Pin your LangGraph version — the HITL API changed in late 2024 (`interrupt()` replaced `NodeInterrupt`)
- Add a cleanup job for stale reviews (user never responds)
- All state must be JSON-serializable — store screenshot URLs, not raw bytes
- Alternative if LangGraph feels heavy: plain async Python + DB state machine (status field: INGESTING → ANALYZING → CAPTURING → GENERATING → PENDING_REVIEW → PUBLISHING → DONE)

---

## COST ANALYSIS (Revised)

### Solo Developer — 50 runs/month
| Component | Cost |
|-----------|------|
| Vercel (Hobby) | Free |
| Railway (FastAPI) | ~$5-7/mo |
| Neon Postgres | Free |
| Claude API (50 runs x $0.06) | ~$3 |
| E2B (50 runs x 3 min) | Free tier covers |
| Cloudflare R2 | Free tier covers |
| LinkedIn API | Free |
| **Total (LinkedIn-only MVP)** | **~$8-10/mo** |

### 100 Users x 10 runs/month (1,000 runs)
| Component | Cost |
|-----------|------|
| Railway | ~$15-25/mo |
| Neon Postgres | ~$20/mo |
| Claude API | ~$60/mo |
| E2B | ~$100-200/mo |
| Cloudflare R2 | ~$5/mo |
| **Total (LinkedIn + Bluesky)** | **~$200-310/mo** |

---

## SECURITY CHECKLIST (Gaps Identified)

| Issue | Severity | Mitigation |
|-------|----------|------------|
| SSRF via GitHub URL | HIGH | Strict regex validation, use GitHub API only, clone only inside E2B |
| Prompt injection via README | MEDIUM-HIGH | Separate LLM calls, system prompt hardening, HITL catches rest |
| OAuth token theft | MEDIUM | Fernet encryption at rest, env-var key, never log tokens, HTTPS only |
| Rate limiting / resource abuse | MEDIUM | Per-user limits (10 runs/hr), queue-based architecture |
| Twitter token rotation failure | MEDIUM | Atomic DB writes on refresh, retry logic, re-auth flow |
| Sandbox crypto mining | LOW | 5-min hard timeout, resource monitoring |
| CSRF | LOW | Bearer token auth + strict CORS on FastAPI mitigates this |

---

## COMPETITORS & MARKET POSITION

**No direct competitor exists.** The closest adjacent tools:
- Social scheduling (Buffer, Typefully) — no repo analysis
- Portfolio generators (Gitfolio) — no social posting
- Repo analytics (CodeScene) — no social content generation

**DevShowcase's unique value:** Automated pipeline from GitHub URL → analyzed project → screenshots → social posts. The sandbox screenshot capability is the killer differentiator.

**Biggest risk:** If sandbox screenshot success rate stays low, the differentiator is weakened. Invest in framework detection and fallback chain quality.

---

## RECOMMENDED PLATFORM STRATEGY (User Decision)

**MVP:** LinkedIn only — validate the core pipeline, keep costs at ~$8-10/mo
**Phase 2:** Add Bluesky (free API, image support, dev community)
**Phase 3:** Add Twitter/X (text-only free tier, or Basic $100/mo when revenue justifies)
**Future:** Dev.to, Mastodon, Threads

---

## LOCAL DEVELOPMENT SETUP

The entire app runs locally on your machine — no hosting needed during development.

### Runs natively (free, no external calls)
| Component | Local Setup |
|-----------|-------------|
| FastAPI backend | `uvicorn src.main:app --reload` on localhost:8000 |
| Next.js frontend | `npm run dev` on localhost:3000 |
| Postgres | Docker: `docker run -p 5432:5432 -e POSTGRES_PASSWORD=dev postgres:16` — or use free remote Neon DB |
| LangGraph | Runs in-process with the backend (just Python code) |

### Requires external API calls (free/cheap)
| Service | Local Dev Cost | Notes |
|---------|---------------|-------|
| Claude API | ~$0.02-0.05 per test run | Needs API key. Can mock responses for unit tests |
| E2B sandbox | Free tier (~100 hrs/mo) | Runs on E2B's cloud. Plenty for dev/testing |
| Cloudflare R2 | **Skip for local dev** | Save screenshots to local disk instead |
| LinkedIn API | Free | Only needed when testing publish. Everything else works without it |

### Local dev startup
```bash
# Terminal 1: Database
docker run -d --name devshowcase-db \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=dev \
  -e POSTGRES_DB=devshowcase \
  postgres:16

# Terminal 2: Backend
cd backend
cp .env.example .env  # add ANTHROPIC_API_KEY, E2B_API_KEY
pip install -e .
uvicorn src.main:app --reload --port 8000

# Terminal 3: Frontend
cd frontend
npm install
npm run dev
```

### What you can test locally without any deployment
- Full ingest → analyze → capture → generate → review pipeline
- SSE live status updates (frontend connects to localhost:8000)
- Screenshot capture via E2B (calls E2B cloud, results come back to your machine)
- Post editing and review UI
- LinkedIn OAuth flow (set callback URL to localhost:3000 in LinkedIn dev app)

### What requires deployment to test
- Production SSE through a real proxy/CDN
- LinkedIn publishing to a real account (OAuth callback must match registered redirect URI — but localhost works if registered)
- Multi-user concurrent access

---

## NEXT STEPS

1. Apply for LinkedIn "Share on LinkedIn" developer product immediately (can take days-weeks)
2. Begin Phase 1 implementation (backend walking skeleton) with the refinements above
3. Set up Neon Postgres + Railway from the start
4. Build the E2B custom template early — it's the highest-risk, highest-value component
