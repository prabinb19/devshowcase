 Agent Gateway — Implementation Plan                                                                                                   
                                               
 Context                             

 DevShowcase currently uses a rigid 4-node LangGraph pipeline (ingest → analyze → capture → generate) that runs on the backend server.
  The new direction: deploy an autonomous AI agent inside an E2B sandbox that does everything — clones, explores, extracts README
 images, generates a LinkedIn post (via Gemini Flash, free), and updates the portfolio site via PR. The narrative: security-focused
 isolated execution, no untrusted code on your infra. The old pipeline code will be removed — agent mode is the only path.

 Key decisions:
 - Agent mode replaces the pipeline (old code removed)
 - Gemini 2.0 Flash (free) as the LLM inside the sandbox
 - Portfolio updates via PR (agent pushes branch, opens PR)
 - Two-way communication: agent can ask questions, user answers via frontend

 ---
 File Changes Overview

 New files

 ┌──────────────────────────────────────────────────┬─────────────────────────────────────────────────┐
 │                       File                       │                     Purpose                     │
 ├──────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
 │ e2b-agent/Dockerfile                             │ E2B template for the agent sandbox              │
 ├──────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
 │ e2b-agent/e2b.toml                               │ E2B template config                             │
 ├──────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
 │ e2b-agent/agent/main.py                          │ Agent entry point (~100 lines)                  │
 ├──────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
 │ e2b-agent/agent/comms.py                         │ File-based IPC helpers (~60 lines)              │
 ├──────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
 │ e2b-agent/agent/explorer.py                      │ Clone + explore repo (~80 lines)                │
 ├──────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
 │ e2b-agent/agent/image_extractor.py               │ Extract/download README images (~50 lines)      │
 ├──────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
 │ e2b-agent/agent/post_generator.py                │ Gemini Flash post generation (~80 lines)        │
 ├──────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
 │ e2b-agent/agent/portfolio_updater.py             │ Clone portfolio, add project, PR (~90 lines)    │
 ├──────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
 │ backend/app/services/agent_executor.py           │ Backend sandbox orchestrator (~200 lines)       │
 ├──────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
 │ backend/alembic/versions/005_add_agent_output.py │ Migration: add agent_output JSON column to runs │
 └──────────────────────────────────────────────────┴─────────────────────────────────────────────────┘

 Modified files

 ┌─────────────────────────────────────┬─────────────────────────────────────────────────────────────────┐
 │                File                 │                             Changes                             │
 ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
 │ backend/app/models/base.py          │ Remove pipeline-only statuses, add agent statuses               │
 ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
 │ backend/app/config.py               │ Add gemini_api_key, portfolio_repo, portfolio_owner             │
 ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
 │ backend/app/routes/runs.py          │ Replace pipeline launch with agent launch, add /answer endpoint │
 ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
 │ backend/app/schemas/runs.py         │ Add agent_output to response, add AgentAnswer schema            │
 ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
 │ backend/app/main.py                 │ Remove init_graph() from lifespan, remove graph import          │
 ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
 │ frontend/src/types/index.ts         │ New statuses, AgentQuestion type, agent_output field            │
 ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
 │ frontend/src/lib/api.ts             │ Add answerAgentQuestion(), update createRun()                   │
 ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
 │ frontend/src/lib/hooks.ts           │ Add pendingQuestion state, handle "question" SSE events         │
 ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
 │ frontend/src/app/runs/[id]/page.tsx │ Agent-mode stepper, question/answer dialog                      │
 ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
 │ frontend/src/app/dashboard/page.tsx │ Remove mode selection (agent-only)                              │
 ├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────┤
 │ backend/pyproject.toml              │ Add google-genai dependency                                     │
 └─────────────────────────────────────┴─────────────────────────────────────────────────────────────────┘

 Files to delete (old pipeline)

 ┌──────────────────────────────────────────────────┬───────────────────────────────────────────────┐
 │                       File                       │                    Reason                     │
 ├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ backend/app/graph.py                             │ LangGraph state graph — replaced by agent     │
 ├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ backend/app/nodes/ingest.py                      │ Agent does its own ingestion                  │
 ├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ backend/app/nodes/analyze.py                     │ Agent does its own analysis                   │
 ├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ backend/app/nodes/capture.py                     │ Agent extracts README images directly         │
 ├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ backend/app/nodes/generate.py                    │ Agent generates via Gemini                    │
 ├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ backend/app/nodes/error_handler.py               │ Agent handles its own errors                  │
 ├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ backend/app/nodes/__init__.py                    │ Empty package                                 │
 ├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ backend/app/services/screenshot/sandbox.py       │ Replaced by agent executor                    │
 ├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ backend/app/services/screenshot/readme_images.py │ Agent handles this                            │
 ├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ backend/app/services/screenshot/project_card.py  │ No more project cards                         │
 ├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ backend/app/services/screenshot/__init__.py      │ Package removal                               │
 ├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ backend/app/services/run_executor.py             │ Replaced by agent_executor                    │
 ├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ backend/app/services/llm_client.py               │ No more server-side Claude calls for pipeline │
 ├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ backend/app/prompts/analyze.py                   │ Prompt lives inside agent now                 │
 ├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ backend/app/prompts/generate.py                  │ Prompt lives inside agent now                 │
 ├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
 │ backend/app/state.py                             │ LangGraph state — not needed                  │
 └──────────────────────────────────────────────────┴───────────────────────────────────────────────┘

 ---
 Implementation Steps

 Step 1: E2B Agent Code (e2b-agent/)

 This is standalone Python that runs inside the sandbox. No dependency on backend code.

 e2b-agent/agent/comms.py — File-based IPC:
 - read_mission() → reads /comms/mission.json
 - update_progress(stage, message) → writes /comms/progress.json
 - set_status(status, error="") → writes /comms/status.json
 - ask_question(text, options=None, timeout=300) → writes /comms/question.json, polls for /comms/answer.json, returns answer string.
 If no answer in timeout, returns empty string (agent uses best guess)

 e2b-agent/agent/explorer.py — Repo exploration:
 - explore_repo(repo_url, github_token) → dict
 - Clones with git clone --depth 1, reads README, walks file tree (cap 500), reads config files (package.json, pyproject.toml, etc.)
 - Returns {repo_url, readme, file_tree, config_files, name}

 e2b-agent/agent/image_extractor.py — README image extraction:
 - extract_images(readme, repo_url) → list[dict]
 - Regex for ![alt](url) patterns, resolves relative URLs to raw.githubusercontent.com
 - Downloads up to 5 images to /output/images/, returns metadata list

 e2b-agent/agent/post_generator.py — Gemini-powered post generation:
 - generate_post(exploration, images, gemini_api_key) → dict
 - Uses google.genai SDK with gemini-2.0-flash
 - System prompt for LinkedIn post writing (hook, body, CTA, first_comment)
 - Returns {platform, body, first_comment, screenshot_urls, alt_texts, status}
 - response_mime_type="application/json" for structured output

 e2b-agent/agent/portfolio_updater.py — Portfolio PR:
 - update_portfolio(exploration, images, mission) → str | None
 - Clones {portfolio_owner}/{portfolio_repo}, creates branch add-project-{name}
 - Reads existing portfolio structure, adds project entry (JSON in _data/projects.json — will need to adapt to actual site structure
 via comms.ask_question if unclear)
 - Commits, pushes branch, creates PR via GitHub API
 - Returns PR URL or None on failure (non-fatal)

 e2b-agent/agent/main.py — Entry point:
 1. read_mission()
 2. update_progress("exploring", "Cloning repository...")
 3. exploration = explore_repo(...)
 4. update_progress("extracting_images", "Extracting images...")
 5. images = extract_images(...)
 6. update_progress("generating", "Generating LinkedIn post...")
 7. post = generate_post(...)
 8. if portfolio configured:
      update_progress("portfolio", "Updating portfolio...")
      pr_url = update_portfolio(...)
 9. Write /output/result.json
 10. set_status("completed")

 e2b-agent/Dockerfile:
 FROM ubuntu:22.04
 RUN apt-get update && apt-get install -y python3 python3-pip git curl
 RUN pip3 install google-genai httpx
 COPY agent/ /agent/
 RUN mkdir -p /comms /output/images /workspace

 Step 2: Database Migration

 backend/alembic/versions/005_add_agent_output.py:
 - Add agent_output JSON column to runs table (nullable)
 - This stores the full agent result (post_draft, images, exploration_log, portfolio_pr_url)

 backend/app/models/base.py — Update RunStatus enum:
 class RunStatus(str, enum.Enum):
     pending = "pending"
     agent_starting = "agent_starting"
     agent_exploring = "agent_exploring"
     agent_generating = "agent_generating"
     agent_awaiting_answer = "agent_awaiting_answer"
     agent_updating_portfolio = "agent_updating_portfolio"
     completed = "completed"
     failed = "failed"

 Add agent_output column to Run model:
 agent_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)

 Step 3: Backend Config

 backend/app/config.py — Add:
 gemini_api_key: str = ""
 portfolio_repo: str = ""         # e.g. "prabinb19.github.io"
 portfolio_owner: str = ""        # e.g. "prabinb19"
 agent_sandbox_timeout: int = 600 # 10 min

 Step 4: Agent Executor Service

 backend/app/services/agent_executor.py — The core orchestrator:

 Data structures:
 - _agent_events: dict[str, asyncio.Queue] — run_id → SSE event queue
 - _agent_sandboxes: dict[str, Sandbox] — run_id → live sandbox
 - _pending_questions: dict[str, dict] — run_id → current question

 start_agent_run(run_id, user_id, repo_url):
 1. Create asyncio.Queue for events
 2. Create E2B sandbox (template=agent template, timeout=600s, envs={CI: true})
 3. Write /comms/mission.json with: repo_url, gemini_api_key, github_token, portfolio_repo, portfolio_owner
 4. Start agent: sandbox.commands.run("python3 /agent/main.py", background=True)
 5. Enter monitor loop

 _monitor_agent(run_id, sandbox, queue):
 - Poll every 2s:
   - Read /comms/status.json → if "completed", read /output/result.json, save to DB, return
   - If "failed", read error, update DB, return
   - Read /comms/progress.json → if changed, push to queue, update run status
   - Read /comms/question.json → if new question_id, push to queue with "question" event type
 - On any exception: set run to failed, cleanup

 submit_answer(run_id, answer_text):
 - Look up sandbox and pending question
 - Write /comms/answer.json with {question_id, text}

 get_event_queue(run_id) → Queue | None

 _cleanup(run_id):
 - Pop from all dicts, kill sandbox

 Step 5: Route Changes

 backend/app/routes/runs.py:

 POST /api/runs — Simplified:
 - Remove compiled_graph check
 - Create Run with status=RunStatus.pending
 - Launch start_agent_run() as background task
 - Return run_id

 GET /api/runs/{run_id}/stream — Rewrite to use agent event queue:
 async def stream_run(run_id):
     queue = get_event_queue(str(run_id))
     if not queue:
         raise HTTPException(404, "No active agent session")

     async def event_generator():
         while True:
             event = await asyncio.wait_for(queue.get(), timeout=30)
             event_type = "question" if "question" in event else "status"
             yield {"event": event_type, "data": json.dumps(event)}
             if event.get("stage") in ("completed", "error"):
                 yield {"event": "done", "data": "complete"}
                 return

     return EventSourceResponse(event_generator(), ping=15)

 POST /api/runs/{run_id}/answer — New endpoint:
 - Body: AgentAnswer {text: str}
 - Calls submit_answer(run_id, text)

 Remove regenerate_run endpoint (not applicable to agent mode — user can start a new run)

 backend/app/schemas/runs.py:
 - Add agent_output: dict | None to RunDetailResponse
 - Add AgentAnswer schema

 backend/app/main.py:
 - Remove init_graph() from lifespan
 - Remove import of app.graph
 - Keep health endpoint (simplify to always return ok)

 Step 6: Frontend Changes

 frontend/src/types/index.ts:
 export type RunStatus =
   | "pending"
   | "agent_starting" | "agent_exploring" | "agent_generating"
   | "agent_awaiting_answer" | "agent_updating_portfolio"
   | "completed" | "failed";

 export interface AgentQuestion {
   question_id: string;
   text: string;
   options?: string[] | null;
 }

 export interface AgentOutput {
   post_draft: PostDraft;
   images: Array<{ url: string; alt_text: string; source: string }>;
   exploration_log: string;
   portfolio_pr_url: string | null;
 }

 // Update RunDetail to include agent_output
 // Update SSEEvent to include optional question field

 frontend/src/lib/hooks.ts — Extend useSSE:
 - Add pendingQuestion state and setPendingQuestion setter
 - Listen for "question" event type → parse and set pendingQuestion
 - Return pendingQuestion and clearQuestion in the hook

 frontend/src/lib/api.ts:
 - Add answerAgentQuestion(runId, text) → POST /api/runs/{runId}/answer

 frontend/src/app/runs/[id]/page.tsx — Agent mode UI:
 - Replace pipeline stages with agent stages:
   - "Starting secure sandbox" → "Exploring repository" → "Generating LinkedIn post" → "Updating portfolio" → "Complete"
 - Add QuestionDialog component: shows when pendingQuestion is set
   - If options provided: render as buttons
   - Otherwise: text input + send button
   - On answer: call answerAgentQuestion(), clear question
 - On completion: navigate to review page (existing review page works, reads post_draft from agent_output)

 frontend/src/app/runs/[id]/review/page.tsx:
 - Read post_draft from run.agent_output.post_draft instead of run.post_draft
 - Show portfolio_pr_url if present ("View Portfolio PR" link)
 - Show exploration_log as a collapsible section

 Step 7: Remove Old Pipeline Code

 Delete the files listed in the "Files to delete" table above. Remove their imports from any remaining files. Remove langgraph,
 e2b-code-interpreter from pyproject.toml dependencies (keep e2b-desktop). Remove checkpoint_url from config.

 Step 8: Update pyproject.toml

 - Add: google-genai (for testing/dev parity, though it runs inside sandbox)
 - Remove: langgraph, langgraph-checkpoint-postgres, psycopg
 - Keep: e2b-desktop (used by agent_executor to create sandboxes)

 ---
 IPC Protocol Summary

 Backend writes:                    Agent writes:
 /comms/mission.json (once)         /comms/status.json (running|completed|failed)
 /comms/answer.json (per question)  /comms/progress.json (per stage change)
                                    /comms/question.json (when stuck)
                                    /output/result.json (final output)
                                    /output/images/*.png (downloaded images)

 ---
 Verification

 1. Unit test agent modules: Run each agent module (explorer, image_extractor, post_generator) with mocked subprocess/httpx/genai
 calls
 2. Integration test: Submit a real public repo URL, watch SSE events in browser devtools, verify:
   - Stages progress: starting → exploring → generating → portfolio → completed
   - Final result has post_draft with body + first_comment
   - Images extracted from README
   - Portfolio PR created (check GitHub)
 3. Question flow: Test with a repo that triggers ambiguity (e.g., monorepo) — verify question appears in frontend, answer flows back,
  agent continues
 4. Failure handling: Kill sandbox mid-run, verify run status becomes "failed" with error message
 5. Review page: Verify post_draft renders correctly, LinkedIn publish still works end-to-end