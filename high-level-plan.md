# DevShowcase Agent — Engineering Design Document

**Author:** Prabin  
**Date:** February 2026  
**Status:** Design Phase  
**Revision:** v2 — Web app architecture, no self-hosted agents

---

## 0. Security Design Philosophy

This project explicitly avoids self-hosted agent runtimes like OpenClaw/Moltbot. Microsoft's Defender Security Research Team published a threat analysis (Feb 2026) classifying these as "untrusted code execution with persistent credentials" — citing skill malware, indirect prompt injection through shared feeds, and memory poisoning as concrete attack vectors.

**DevShowcase's security posture:**
- **No code runs on the user's personal machine.** Everything executes in cloud sandboxes (E2B) that are destroyed after each run.
- **No persistent agent memory** that can be poisoned across sessions. State is explicit LangGraph state, inspectable and resettable.
- **No third-party skill/plugin system.** The pipeline is fixed, auditable code — not dynamically loaded from a public registry.
- **Human-in-the-loop is mandatory.** Nothing posts without explicit user approval in the web UI.
- **OAuth tokens are encrypted at rest** on the server, never on the user's device.
- **Sandboxed execution only.** Untrusted repo code runs exclusively inside E2B Firecracker microVMs with no access to credentials or host filesystem.

---

## 1. Problem Statement

A developer builds a project, pushes to GitHub, and then... nothing. The project sits there invisible. Sharing it on LinkedIn/Twitter requires: understanding the project enough to write a good post, taking screenshots, formatting for each platform, and actually posting. This friction means most projects never get shared.

**Goal:** Build a web application where a developer pastes a GitHub URL, the system analyzes the project, captures screenshots via cloud sandbox, generates platform-optimized social posts, presents them for human review/editing, and publishes on approval.

---

## 2. High-Level Architecture

```
┌─ FRONTEND (Next.js on Vercel) ──────────────────────────────────┐
│                                                                  │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ URL Input  │  │ Live Status  │  │ Review & Edit UI         │ │
│  │ + Auth     │  │ Pipeline     │  │ ┌─────────┐ ┌─────────┐ │ │
│  │ (LinkedIn, │  │ Progress     │  │ │LinkedIn │ │Twitter  │ │ │
│  │  Twitter)  │  │ via SSE      │  │ │ Draft   │ │ Draft   │ │ │
│  └─────┬──────┘  └──────────────┘  │ │ [Edit]  │ │ [Edit]  │ │ │
│        │                            │ └─────────┘ └─────────┘ │ │
│        │                            │ [Approve & Post] [Skip] │ │
│        │                            └──────────────────────────┘ │
└────────┼────────────────────────────────────────────────────────┘
         │ HTTPS
┌────────▼─────── BACKEND (Python FastAPI on Railway/Fly) ────────┐
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ INGEST   │─▶│ ANALYZE  │─▶│ CAPTURE  │─▶│   GENERATE     │  │
│  │ GitHub   │  │ Claude   │  │ E2B +    │  │   Post Drafts  │  │
│  │ API      │  │ API      │  │Playwright│  │   per Platform │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────┬────────┘  │
│                                                     │           │
│  ┌──────────────────────────────────────────────────▼────────┐  │
│  │ State stored in DB (SQLite/Postgres) — inspectable,       │  │
│  │ no poisonable "memory." User reviews in frontend.         │  │
│  │ On approval → PUBLISH to LinkedIn API + Twitter/X API     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  OAuth tokens: encrypted at rest (Fernet), never sent to client │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Technology Choices (with Rationale)

| Layer | Choice | Why |
|---|---|---|
| **Frontend** | Next.js 14 (App Router) on Vercel | Free hosting, SSE support for live pipeline status, great portfolio demo, React ecosystem |
| **Backend** | Python FastAPI on Railway ($5/mo) or Fly.io | Async-native, lightweight, good LangGraph integration, WebSocket/SSE support |
| **Orchestration** | LangGraph (Python) | Native state machines, checkpointing to DB, clean async pipeline |
| **LLM** | Claude Sonnet 4.5 via API | Best cost/quality ratio for code understanding, 200K context handles large READMEs |
| **Sandbox** | E2B Code Interpreter + Desktop Sandbox | 150ms cold start, Firecracker microVMs, pre-built browser support, Python/JS SDK |
| **Screenshot** | Playwright (inside E2B sandbox) | Auto-wait, multi-browser, battle-tested, never touches host |
| **Social APIs** | LinkedIn REST API (Posts API v202502) + X API v2 (Free tier) | Direct, no middleware dependency |
| **Auth (user login)** | NextAuth.js with GitHub OAuth | Users log in with GitHub — natural for developers, gives us their GitHub token for free |
| **Auth (social posting)** | OAuth2 flows for LinkedIn + Twitter, tokens encrypted server-side | User connects accounts once, tokens stored in DB encrypted with Fernet |
| **Database** | SQLite (MVP) → Postgres (scale) | Store pipeline runs, drafts, publish history, encrypted tokens |
| **Image Storage** | Supabase Storage (free tier) or Cloudflare R2 | Hold generated screenshots for upload to social platforms |

---

## 4. Detailed Pipeline — Stage by Stage

### Stage 1: INGEST — Acquire the Repository

**Input:** GitHub URL or local folder path.

**Implementation:**

```
Node: ingest_repo
├── IF github URL:
│   ├── Parse owner/repo from URL
│   ├── GitHub REST API (with GITHUB_TOKEN):
│   │   ├── GET /repos/{owner}/{repo}           → metadata (description, stars, language, topics)
│   │   ├── GET /repos/{owner}/{repo}/readme     → README content (base64 → decode)
│   │   ├── GET /repos/{owner}/{repo}/git/trees/main?recursive=1  → full file tree
│   │   ├── GET /repos/{owner}/{repo}/languages  → language breakdown
│   │   └── GET /repos/{owner}/{repo}/contents/{path}  → key config files
│   └── Fetch key config files based on tree:
│       ├── package.json, tsconfig.json (JS/TS projects)
│       ├── requirements.txt, pyproject.toml, setup.py (Python)
│       ├── Cargo.toml (Rust), go.mod (Go), Dockerfile, docker-compose.yml
│       └── Any file matching: *config*, *.env.example, Makefile
│
├── IF local folder:
│   ├── Walk directory tree (respect .gitignore via pathspec lib)
│   ├── Read README.md, config files same as above
│   ├── Generate same metadata structure as GitHub API would
│   └── Optionally: check for .git remote to extract GitHub URL
│
└── OUTPUT → RepoContext object:
    {
      metadata: { name, description, stars, forks, language, topics, url },
      readme: string (raw markdown),
      file_tree: string[] (paths),
      config_files: { [filename]: content },
      images_in_readme: string[] (extracted image URLs from markdown)
    }
```

**Key engineering decisions:**
- Use a fine-grained GitHub PAT with `public_repo` read scope. For private repos, the user adds broader scope.
- Rate limit: GitHub API allows 5,000 req/hr with auth. A single repo ingest uses ~5-10 calls. No concern.
- File tree: fetch recursively but cap at 10,000 entries. For monorepos, focus on root-level structure.
- Config file fetch: limit to files < 50KB to avoid blowing up context.

---

### Stage 2: ANALYZE — Understand the Project

**Input:** RepoContext object.

**Implementation:**

```
Node: analyze_project
├── Construct LLM prompt with:
│   ├── README (truncated to ~8K tokens if massive)
│   ├── File tree (top 500 paths)
│   ├── Key config files
│   └── Metadata (stars, language, topics)
│
├── LLM Call #1: Project Analysis (structured output via tool_use)
│   └── Returns ProjectAnalysis:
│       {
│         project_type: "web_app" | "cli_tool" | "library" | "api_service" |
│                       "mobile_app" | "ml_model" | "devtool" | "other",
│         summary: string (2-3 sentences, what it does and why it matters),
│         tech_stack: string[] (e.g., ["Next.js", "TypeScript", "Prisma", "PostgreSQL"]),
│         key_features: string[] (top 3-5 selling points),
│         run_command: string | null (how to start it: "npm run dev", "python app.py", etc.),
│         expected_port: number | null (3000, 8080, etc.),
│         install_command: string | null ("npm install", "pip install -r requirements.txt"),
│         has_dockerfile: boolean,
│         visual_type: "web_ui" | "cli_output" | "api_only" | "notebook" | "mobile",
│         notable_stats: string | null ("2.5K stars", "used by X company"),
│         readme_has_images: boolean
│       }
│
├── Determine screenshot strategy based on analysis:
│   ├── IF readme_has_images AND images_in_readme.length > 0:
│   │   └── strategy = "extract_readme_images"
│   ├── ELIF visual_type == "web_ui" AND run_command != null:
│   │   └── strategy = "sandbox_screenshot"
│   ├── ELIF visual_type == "cli_output":
│   │   └── strategy = "sandbox_terminal_capture"
│   ├── ELIF visual_type == "api_only" OR visual_type == "notebook":
│   │   └── strategy = "generate_project_card"
│   └── ELSE:
│       └── strategy = "generate_project_card"
│
└── OUTPUT → ProjectAnalysis + screenshot_strategy
```

**Key engineering decisions:**
- Use Claude's tool_use/structured output to enforce the schema. No regex parsing of free text.
- The `run_command` detection is critical for sandbox success. LLM reads `package.json` scripts, `Makefile` targets, `Dockerfile` CMD, etc. to infer this. Include a fallback heuristic: if `package.json` has a `dev` script → `npm run dev`, etc.
- Keep the analysis prompt under 12K tokens total. This is a single, focused LLM call — not a chat.

---

### Stage 3: CAPTURE — Get Visual Proof

This is the most complex and failure-prone stage. Design for graceful degradation.

```
Node: capture_visuals
├── Strategy A: "extract_readme_images"
│   ├── Parse image URLs from README markdown
│   │   └── Regex: /!\[.*?\]\((.*?)\)/g + HTML <img> tags
│   ├── Resolve relative URLs → absolute (github raw content URL)
│   ├── Download top 3 images
│   ├── Validate: is it an actual image? (check Content-Type header)
│   ├── Resize/optimize for social media (1200x630 for LinkedIn, 1600x900 for Twitter)
│   └── OUTPUT → Screenshot[] (image buffers + metadata)
│
├── Strategy B: "sandbox_screenshot"
│   ├── Create E2B sandbox (template: "base" or custom with Node+Python pre-installed)
│   ├── Clone repo inside sandbox:
│   │   └── sandbox.commands.run("git clone {url} /app && cd /app")
│   ├── Install dependencies:
│   │   └── sandbox.commands.run(install_command, timeout=120s)
│   │   └── IF fails: try Dockerfile build instead
│   ├── Start the dev server:
│   │   └── sandbox.commands.run(run_command, background=True)
│   │   └── Wait for port to be available (poll localhost:{port} every 2s, timeout 60s)
│   ├── Take screenshots with Playwright (installed in sandbox):
│   │   ├── Navigate to http://localhost:{port}
│   │   ├── Wait for network idle (networkidle event)
│   │   ├── Full page screenshot → hero image
│   │   ├── Viewport screenshot (1280x720) → social preview
│   │   └── Optional: if SPA detected, wait extra 3s for JS render
│   ├── Download screenshots from sandbox
│   ├── Teardown sandbox
│   └── OUTPUT → Screenshot[]
│   
│   FALLBACK CHAIN (if any step fails):
│   ├── Try Docker build if native install fails
│   ├── Try extracting README images if sandbox fails entirely
│   └── Fall through to "generate_project_card" as last resort
│
├── Strategy C: "sandbox_terminal_capture"
│   ├── Create E2B sandbox
│   ├── Clone + install
│   ├── Run CLI with --help or example command
│   ├── Capture terminal output as text
│   ├── Render terminal output to image using:
│   │   └── carbon.now.sh API OR silicon (Rust CLI) OR custom HTML→Playwright render
│   ├── Teardown sandbox
│   └── OUTPUT → Screenshot[]
│
├── Strategy D: "generate_project_card"
│   ├── Create a styled HTML card with:
│   │   ├── Project name + description
│   │   ├── Tech stack icons (use devicon CDN or simple-icons)
│   │   ├── Stars/forks badges
│   │   └── Key features as bullet points
│   ├── Render HTML to image via Playwright (local or sandbox)
│   └── OUTPUT → Screenshot[]
│
└── Upload all screenshots to temp storage (Supabase Storage / S3)
    └── Return public URLs for use in social posts
```

**Key engineering decisions:**

- **Timeout budget:** The entire capture stage gets a 180-second hard timeout. Sandbox creation (~1s) + clone (~5s) + install (~60s) + server start (~30s) + screenshot (~10s) = ~106s typical. Leaves buffer.
- **E2B sandbox template:** Pre-build a custom template with Node 20, Python 3.12, Playwright, and common build tools already installed. This cuts install time significantly. Use `e2b template build` with a Dockerfile.
- **Port detection:** If `expected_port` is null, scan common ports (3000, 3001, 5000, 5173, 8000, 8080) with a parallel port check.
- **Sandbox cost:** E2B charges per second of compute. A typical run is ~2 minutes = ~$0.01-0.03. Acceptable.
- **Image optimization:** Before upload, resize to max 2048px wide, compress to <1MB. LinkedIn and Twitter both have upload size limits.

---

### Stage 4: GENERATE — Craft Platform-Specific Posts

**Input:** ProjectAnalysis + Screenshot URLs.

```
Node: generate_posts
├── LLM Call #2: Generate LinkedIn Post
│   ├── System prompt: persona, formatting rules, character limits
│   ├── Rules:
│   │   ├── Max 3,000 characters (LinkedIn limit)
│   │   ├── Hook in first 2 lines (before "see more" fold)
│   │   ├── Include 3-5 relevant hashtags at the bottom
│   │   ├── Tone: authentic builder sharing work, not salesy
│   │   ├── Mention specific tech decisions and why
│   │   ├── Include a call-to-action (star it, try it, feedback welcome)
│   │   └── If it's the user's own project: first person. If sharing others': third person.
│   └── OUTPUT → linkedin_post: string
│
├── LLM Call #3: Generate Twitter/X Post
│   ├── Rules:
│   │   ├── Max 280 characters for single tweet
│   │   ├── OR: thread format (3-5 tweets, each ≤ 280 chars)
│   │   ├── First tweet must hook (project name + one-liner + emoji)
│   │   ├── Include GitHub link in last tweet
│   │   ├── 1-3 hashtags max (Twitter culture: fewer is better)
│   │   └── Conversational, punchy, developer-to-developer tone
│   └── OUTPUT → twitter_posts: string[] (array of tweets for thread)
│
├── LLM Call #4 (optional): Generate Alt Text for screenshots
│   └── Accessibility: describe what the screenshot shows for screen readers
│
└── OUTPUT → PostDraft:
    {
      linkedin: { text: string, image_urls: string[], hashtags: string[] },
      twitter: { thread: string[], image_urls: string[], hashtags: string[] },
      alt_texts: string[]
    }
```

**Prompt engineering notes:**
- Feed the LLM 3-5 examples of high-performing developer posts from LinkedIn/Twitter as few-shot examples in the system prompt.
- Include the user's typical posting style if available (future feature: analyze their last 10 posts and mimic tone).
- CRITICAL: The LLM must NOT hallucinate features. Ground it strictly in the README and analysis.

---

### Stage 5: REVIEW — Human in the Loop (Web UI)

This is non-negotiable. Nothing posts without explicit user action in the browser.

```
The frontend polls or subscribes (SSE) to the pipeline run status.
When GENERATE completes, the UI transitions to the Review screen:

┌─────────────────────────────────────────────────────────┐
│  DevShowcase — Review Your Post                         │
│─────────────────────────────────────────────────────────│
│                                                         │
│  Project: awesome-cli-tool                              │
│  Summary: A Go CLI that does X, Y, Z                    │
│  Tech: Go, Cobra, SQLite                                │
│                                                         │
│  📸 Screenshots:                                        │
│  [img1_thumb] [img2_thumb] [img3_thumb]   [Regenerate]  │
│                                                         │
│  ┌─────────────────────┐ ┌─────────────────────┐       │
│  │ LinkedIn Post       │ │ Twitter Thread      │       │
│  │                     │ │                     │       │
│  │ [editable textarea] │ │ Tweet 1: [edit]     │       │
│  │                     │ │ Tweet 2: [edit]     │       │
│  │ 1,847 / 3,000 chars │ │ Tweet 3: [edit]     │       │
│  │                     │ │ 234 / 280 chars ea  │       │
│  │ ☑ Post to LinkedIn  │ │ ☑ Post to Twitter   │       │
│  └─────────────────────┘ └─────────────────────┘       │
│                                                         │
│  [🔄 Regenerate with feedback: _______________]         │
│  [✅ Approve & Publish]  [⏭ Save as Draft]  [🗑 Cancel]│
│                                                         │
└─────────────────────────────────────────────────────────┘

Backend flow:
├── "Approve & Publish":
│   └── Backend receives POST /api/runs/{id}/publish
│       ├── Validates user session (NextAuth JWT)
│       ├── Reads approved draft from DB
│       └── Triggers PUBLISH stage
├── "Regenerate with feedback":
│   ├── User types: "make it more casual" or "mention the Go part more"
│   └── POST /api/runs/{id}/regenerate { feedback: "..." }
│       └── Re-runs GENERATE with feedback appended to prompt
├── "Save as Draft":
│   └── Stores current state in DB, user can return later
└── "Cancel":
    └── Marks run as cancelled, cleans up screenshots from storage
```

---

### Stage 6: PUBLISH — Post to Platforms

```
Node: publish_posts
├── LinkedIn Publishing:
│   ├── Step 1: Upload image(s)
│   │   ├── POST /rest/images?action=initializeUpload
│   │   │   Body: { initializeUploadRequest: { owner: "urn:li:person:{id}" } }
│   │   ├── Response → uploadUrl + image URN
│   │   ├── PUT {uploadUrl} with binary image data
│   │   └── Store image URN for post creation
│   ├── Step 2: Create post
│   │   ├── POST /rest/posts
│   │   │   Headers:
│   │   │     LinkedIn-Version: 202502
│   │   │     X-Restli-Protocol-Version: 2.0.0
│   │   │   Body: {
│   │   │     author: "urn:li:person:{id}",
│   │   │     commentary: "{post_text}",
│   │   │     visibility: "PUBLIC",
│   │   │     distribution: { feedDistribution: "MAIN_FEED" },
│   │   │     content: { media: { id: "{image_urn}" } },
│   │   │     lifecycleState: "PUBLISHED"
│   │   │   }
│   │   └── Response → 201 Created + post URN
│   └── Store post URL for confirmation
│
├── Twitter/X Publishing:
│   ├── Step 1: Upload media (Free tier: 85 media uploads/24hrs)
│   │   ├── POST /2/media/upload (init) → media_id
│   │   ├── POST /2/media/upload/{id}/append (upload chunks)
│   │   ├── POST /2/media/upload/{id}/finalize
│   │   └── Store media_id
│   ├── Step 2: Post thread
│   │   ├── POST /2/tweets { text: thread[0], media: { media_ids: [media_id] } }
│   │   │   → tweet_id_1
│   │   ├── FOR remaining tweets in thread:
│   │   │   POST /2/tweets { text: thread[n], reply: { in_reply_to_tweet_id: previous_id } }
│   │   └── Collect all tweet IDs
│   └── Store thread URL
│
└── OUTPUT → PublishResult:
    {
      linkedin: { success: bool, url: string, error?: string },
      twitter: { success: bool, url: string, error?: string }
    }
```

**Key engineering decisions:**

- **LinkedIn OAuth2:** Requires a LinkedIn Developer App with "Share on LinkedIn" + "Sign In with LinkedIn using OpenID Connect" products enabled. Token refresh: access tokens expire in 60 days, refresh tokens in 365 days. Build automatic refresh.
- **Twitter/X Free Tier:** Allows 1,500 tweets/month write and 85 media uploads/day. Plenty for personal use. No read access, so you can't verify the post was published by reading it back — just check the 201 response.
- **Token storage:** Encrypt OAuth tokens at rest. Use `cryptography.fernet` (Python) with a key from env var. Store in SQLite for simplicity, or a proper secrets manager in production.
- **Retry logic:** Both APIs can 429 rate-limit you. Implement exponential backoff with jitter. Max 3 retries.
- **Image format:** LinkedIn accepts PNG, JPG, GIF ≤ 10MB. Twitter accepts PNG, JPG, GIF, WEBP ≤ 5MB. Normalize to JPG, max 1MB.

---

## 5. Data Model

```python
@dataclass
class RepoContext:
    url: str | None
    local_path: str | None
    metadata: RepoMetadata       # name, description, stars, language, topics
    readme: str
    file_tree: list[str]
    config_files: dict[str, str]
    images_in_readme: list[str]

@dataclass
class ProjectAnalysis:
    project_type: Literal["web_app", "cli_tool", "library", "api_service", "ml_model", "devtool", "other"]
    summary: str
    tech_stack: list[str]
    key_features: list[str]
    run_command: str | None
    install_command: str | None
    expected_port: int | None
    has_dockerfile: bool
    visual_type: Literal["web_ui", "cli_output", "api_only", "notebook", "mobile"]
    screenshot_strategy: Literal["extract_readme_images", "sandbox_screenshot", "sandbox_terminal_capture", "generate_project_card"]

@dataclass
class Screenshot:
    url: str           # public URL after upload to storage
    alt_text: str
    source: str        # "readme", "sandbox", "generated"
    width: int
    height: int

@dataclass
class PostDraft:
    linkedin_text: str
    twitter_thread: list[str]
    screenshots: list[Screenshot]
    review_status: Literal["pending", "approved", "edited", "rejected"]

@dataclass
class PublishResult:
    platform: str
    success: bool
    post_url: str | None
    error: str | None
    published_at: datetime | None
```

---

## 6. LangGraph State & Graph Definition

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated

class AgentState(TypedDict):
    repo_input: str                          # GitHub URL or local path
    repo_context: RepoContext | None
    analysis: ProjectAnalysis | None
    screenshots: list[Screenshot]
    post_draft: PostDraft | None
    user_feedback: str | None                # from HITL
    publish_result: dict | None
    error: str | None
    current_stage: str

# Build the graph
graph = StateGraph(AgentState)

graph.add_node("ingest", ingest_repo)
graph.add_node("analyze", analyze_project)
graph.add_node("capture", capture_visuals)
graph.add_node("generate", generate_posts)
graph.add_node("review", human_review)          # interrupt node
graph.add_node("publish", publish_posts)
graph.add_node("handle_error", handle_error)

graph.set_entry_point("ingest")
graph.add_edge("ingest", "analyze")
graph.add_edge("analyze", "capture")
graph.add_edge("capture", "generate")
graph.add_edge("generate", "review")

# Conditional after review
graph.add_conditional_edges("review", route_after_review, {
    "publish": "publish",
    "regenerate": "generate",
    "cancel": END,
})
graph.add_edge("publish", END)

# Error edges from any node
for node in ["ingest", "analyze", "capture", "generate", "publish"]:
    graph.add_edge(node, "handle_error")  # on exception

app = graph.compile(checkpointer=SqliteSaver(conn))
```

---

## 7. Error Handling & Resilience

| Failure | Impact | Mitigation |
|---|---|---|
| GitHub API rate limit | Ingest fails | Check `X-RateLimit-Remaining` header, wait if < 10 |
| README too large (>100KB) | Context overflow | Truncate to first 8K tokens, note truncation |
| Sandbox install fails | No screenshot | Fallback chain: Docker → README images → project card |
| Server doesn't start in sandbox | No screenshot | Try alternate ports, check for build errors in stdout |
| Playwright navigation timeout | No screenshot | Retry once with longer timeout (30s), then fallback |
| LLM returns malformed output | Bad drafts | Use structured output/tool_use, validate schema, retry once |
| LinkedIn token expired | Publish fails | Auto-refresh with refresh_token, re-auth if refresh fails |
| Twitter 429 rate limit | Publish delayed | Exponential backoff, queue for retry in 15 min |
| E2B sandbox timeout | No screenshot | 180s hard limit, graceful fallback to project card |

**Global error strategy:** Every node wraps its logic in try/except. On failure, state.error is set and the graph routes to `handle_error` which logs, notifies the user, and determines if a fallback path exists.

---

## 8. Security Considerations

- **OAuth tokens:** Encrypted at rest with Fernet symmetric encryption. Key from `ENCRYPTION_KEY` env var. Never logged.
- **E2B sandboxes:** Fully isolated Firecracker microVMs. Untrusted repo code runs ONLY inside the sandbox, never on the host.
- **GitHub token:** Fine-grained PAT with minimal scope (`public_repo:read`). Stored same as OAuth tokens.
- **User data:** No analytics, no tracking. Drafts stored locally or in user's own storage. Publish results logged for user's reference only.
- **Secrets in repos:** The agent should NEVER include `.env` file contents, API keys, or secrets found in the repo in posts. Add explicit filtering in the analyze step.

---

## 9. Cost Estimation (Per Run)

| Component | Cost |
|---|---|
| Claude Sonnet 4.5 (3 LLM calls, ~15K tokens total) | ~$0.05 |
| E2B sandbox (2 min compute) | ~$0.02 |
| Supabase Storage (3 images, ~3MB) | ~$0.001 |
| LinkedIn API | Free |
| Twitter/X API (Free tier) | Free |
| **Total per project showcase** | **~$0.07** |

---

## 10. Implementation Roadmap

### Phase 1: Backend Walking Skeleton (Week 1-2)
- [ ] Set up Python project: `pyproject.toml`, deps (langgraph, anthropic, e2b, httpx, Pillow)
- [ ] FastAPI server with `/api/runs` endpoint (create a run, get status)
- [ ] Implement `ingest_repo` node (GitHub API only)
- [ ] Implement `analyze_project` node with Claude structured output
- [ ] SSE endpoint for live pipeline status updates
- [ ] Unit tests for ingest + analyze with mock GitHub API responses

### Phase 2: Next.js Frontend + Auth (Week 3-4)
- [ ] Next.js 14 App Router project, deploy to Vercel
- [ ] NextAuth.js with GitHub OAuth (login with GitHub)
- [ ] URL input page: paste GitHub link → kick off pipeline
- [ ] Live status page: SSE connection shows pipeline progress
- [ ] Basic review page: display analysis + drafts as read-only (editing comes later)
- [ ] Connect frontend to backend API

### Phase 3: Screenshot Pipeline (Week 5-6)
- [ ] Build custom E2B template (Dockerfile with Node, Python, Playwright)
- [ ] Implement Strategy A: extract README images
- [ ] Implement Strategy B: sandbox screenshot (web apps)
- [ ] Implement Strategy D: project card generator (HTML → Playwright → PNG)
- [ ] Fallback chain logic
- [ ] Upload to Supabase Storage, return public URLs
- [ ] Integration tests: feed 10 diverse repos, verify screenshots captured

### Phase 4: Post Generation + Review UI (Week 7-8)
- [ ] Craft system prompts for LinkedIn and Twitter formats
- [ ] Implement `generate_posts` node
- [ ] Build few-shot example bank (10 high-performing dev posts per platform)
- [ ] Full review UI: editable textareas, character counts, platform toggles
- [ ] "Regenerate with feedback" flow
- [ ] Save as draft / resume later functionality
- [ ] Screenshot preview with selection (pick which images to attach)

### Phase 5: OAuth + Publishing (Week 9-10)
- [ ] LinkedIn OAuth2 flow: connect account page in settings
- [ ] Twitter/X OAuth2 PKCE flow: connect account page in settings
- [ ] Encrypted token storage (Fernet + server-side DB)
- [ ] Token refresh logic (LinkedIn: 60-day expiry, Twitter: 2-hour with refresh)
- [ ] Implement PUBLISH stage: image upload + post creation for both platforms
- [ ] End-to-end test: URL → published post on both platforms
- [ ] Retry logic and error handling for all publish paths
- [ ] Post history page: log of all published posts with links

### Phase 6: Polish & Launch (Week 11-12)
- [ ] Landing page (what it does, demo GIF, security philosophy)
- [ ] User preferences: default tone, hashtag preferences
- [ ] Rate limiting dashboard (API budget remaining)
- [ ] Error states and empty states throughout the UI
- [ ] Mobile-responsive review UI
- [ ] Open source the project, write README
- [ ] Deploy and showcase it... using itself 🔄

### Phase 7: Advanced (Future)
- [ ] Scheduled posting ("post this tomorrow at 9am EST")
- [ ] Batch mode ("showcase all my pinned repos")
- [ ] Analytics: which posts performed best → improve prompts
- [ ] GitHub Action: auto-showcase on new release tag
- [ ] Additional platforms: Bluesky, Dev.to, Mastodon
- [ ] Team mode: multiple users, shared post queue
- [ ] Local folder upload (drag-and-drop zip in the web UI)

---

## 11. Testing Strategy

**Unit tests:**
- GitHub API response parsing (mock responses)
- README image URL extraction (edge cases: relative URLs, HTML img tags, base64 images)
- LLM output schema validation
- Image resizing and format conversion
- OAuth token encryption/decryption

**Integration tests:**
- Full pipeline with 10 curated repos (known good repos with varied types)
- Sandbox screenshot capture (web app repo: create-react-app, Flask app)
- Publish to test LinkedIn/Twitter accounts (use dedicated test accounts)

**Evaluation suite:**
- 50 diverse repos → generate posts → human rate on: accuracy, engagement potential, tone appropriateness
- Track: screenshot success rate (target: >80%), post generation quality (target: >4/5 avg)

---

## 12. Key Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LinkedIn deprecates/changes Posts API | Medium | High | Abstract behind interface, monitor Microsoft Learn changelog |
| Twitter/X raises Free tier price or kills it | Medium | High | Build Bluesky as backup platform from day one |
| Many repos can't be run in sandbox | High | Medium | Fallback chain handles this; project card is always available |
| LLM hallucinates project features | Medium | High | Ground on README only, add verification step, HITL catches rest |
| E2B pricing changes | Low | Medium | Sandbox logic is abstracted; could swap to self-hosted Docker |

---

## 13. File Structure

```
devshowcase/
├── README.md
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── backend/                          # Python FastAPI + LangGraph
│   ├── pyproject.toml
│   ├── .env.example
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app, CORS, routes
│   │   ├── graph.py                  # LangGraph definition
│   │   ├── state.py                  # AgentState + dataclasses
│   │   ├── routes/
│   │   │   ├── runs.py               # POST /runs, GET /runs/{id}, SSE status
│   │   │   ├── auth.py               # OAuth callback endpoints (LinkedIn, Twitter)
│   │   │   └── publish.py            # POST /runs/{id}/publish, /regenerate
│   │   ├── nodes/
│   │   │   ├── ingest.py             # GitHub API ingestion
│   │   │   ├── analyze.py            # LLM project analysis
│   │   │   ├── capture/
│   │   │   │   ├── __init__.py       # Strategy router
│   │   │   │   ├── readme_images.py  # Extract images from README
│   │   │   │   ├── sandbox.py        # E2B + Playwright screenshot
│   │   │   │   ├── terminal.py       # CLI output capture
│   │   │   │   └── project_card.py   # Generate visual card
│   │   │   ├── generate.py           # Post generation (LinkedIn + Twitter)
│   │   │   └── publish/
│   │   │       ├── linkedin.py       # LinkedIn API client
│   │   │       └── twitter.py        # Twitter/X API client
│   │   ├── auth/
│   │   │   ├── linkedin_oauth.py     # OAuth2 flow + token refresh
│   │   │   ├── twitter_oauth.py      # OAuth2 PKCE flow
│   │   │   └── token_store.py        # Encrypted token storage (Fernet)
│   │   ├── storage/
│   │   │   └── image_store.py        # Upload/manage screenshots
│   │   ├── db/
│   │   │   ├── models.py             # SQLAlchemy models (User, Run, Draft, Token)
│   │   │   └── database.py           # DB connection + migrations
│   │   ├── prompts/
│   │   │   ├── analyze.py            # Analysis system prompt
│   │   │   ├── linkedin.py           # LinkedIn post generation prompt
│   │   │   ├── twitter.py            # Twitter thread generation prompt
│   │   │   └── examples.py           # Few-shot examples bank
│   │   └── utils/
│   │       ├── markdown.py           # README parsing utilities
│   │       ├── image.py              # Resize, compress, format conversion
│   │       └── retry.py              # Exponential backoff helper
│   ├── templates/
│   │   └── project_card.html         # HTML template for project cards
│   └── tests/
│       ├── test_ingest.py
│       ├── test_analyze.py
│       ├── test_capture.py
│       ├── test_generate.py
│       ├── test_publish.py
│       └── fixtures/                 # Mock API responses, sample READMEs
│
├── frontend/                         # Next.js 14 App Router
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── app/
│   │   ├── layout.tsx                # Root layout + NextAuth provider
│   │   ├── page.tsx                  # Landing page / URL input
│   │   ├── dashboard/
│   │   │   ├── page.tsx              # Run history list
│   │   │   └── [runId]/
│   │   │       └── page.tsx          # Pipeline status + Review UI
│   │   ├── settings/
│   │   │   └── page.tsx              # Connect LinkedIn/Twitter accounts
│   │   └── api/
│   │       └── auth/
│   │           └── [...nextauth]/
│   │               └── route.ts      # NextAuth GitHub OAuth
│   ├── components/
│   │   ├── url-input.tsx             # GitHub URL input + submit
│   │   ├── pipeline-status.tsx       # Live SSE status display
│   │   ├── review-panel.tsx          # Side-by-side LinkedIn + Twitter editors
│   │   ├── screenshot-gallery.tsx    # Screenshot preview + selection
│   │   ├── post-preview.tsx          # Platform-specific preview mockup
│   │   └── publish-history.tsx       # Past posts with links
│   └── lib/
│       ├── api.ts                    # Backend API client
│       └── auth.ts                   # NextAuth config
│
└── docker-compose.yml                # Local dev: backend + DB
```