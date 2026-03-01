export type RunStatus =
  | "pending"
  | "agent_starting"
  | "agent_exploring"
  | "agent_generating"
  | "agent_awaiting_answer"
  | "agent_updating_portfolio"
  | "completed"
  | "failed";

export type DraftStatus = "draft" | "published" | "archived";

export interface RunDetail {
  id: string;
  user_id: string;
  repo_url: string;
  status: RunStatus;
  error: string | null;
  repo_context: Record<string, unknown> | null;
  analysis: Record<string, unknown> | null;
  screenshots: Record<string, unknown>[] | null;
  post_draft: PostDraft | null;
  agent_output: AgentOutput | null;
  created_at: string;
  updated_at: string;
}

export interface PostDraft {
  platform: string;
  body: string;
  first_comment: string;
  screenshot_urls: string[];
  alt_texts: string[];
  status: string;
}

export interface Draft {
  id: string;
  run_id: string;
  user_id: string;
  platform: string;
  body: string;
  first_comment: string | null;
  screenshot_urls: string[] | null;
  alt_texts: string[] | null;
  status: DraftStatus;
  published_url: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateDraftRequest {
  run_id: string;
  user_id: string;
  body: string;
  first_comment?: string;
  screenshot_urls?: string[];
  alt_texts?: string[];
}

export interface UpdateDraftRequest {
  body?: string;
  first_comment?: string;
  screenshot_urls?: string[];
  alt_texts?: string[];
  status?: DraftStatus;
}

export interface CreateRunRequest {
  repo_url: string;
}

export interface RunResponse {
  run_id: string;
  status: RunStatus;
}

export interface SSEEvent {
  stage: string;
  message: string;
  stream_url?: string | null;
  question?: AgentQuestion | null;
}

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

export interface LinkedInStatus {
  connected: boolean;
  expires_at: string | null;
}

export interface PublishResponse {
  success: boolean;
  post_url: string | null;
  error: string | null;
}

export type ToneOption = "professional" | "casual" | "technical" | "enthusiastic";

export interface UserSettings {
  default_tone: ToneOption;
  hashtags: string[];
}
