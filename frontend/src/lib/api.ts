/**
 * API client — all authenticated calls go through the Next.js proxy at
 * /api/backend which attaches a signed JWT. SSE streams and unauthenticated
 * reads still hit the backend directly.
 */

const DIRECT_API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const PROXY_BASE = "/api/backend";

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  { direct = false }: { direct?: boolean } = {}
): Promise<T> {
  const base = direct ? DIRECT_API_BASE : PROXY_BASE;
  const url = `${base}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `API error: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// Runs — authenticated via proxy (no more X-GitHub-* headers)
export function createRun(repoUrl: string) {
  return apiFetch<{ run_id: string; status: string; stream_token: string }>("/api/runs", {
    method: "POST",
    body: JSON.stringify({ repo_url: repoUrl }),
  });
}

export function getRun(runId: string) {
  return apiFetch<import("@/types").RunDetail>(`/api/runs/${runId}`);
}

export function answerAgentQuestion(runId: string, text: string) {
  return apiFetch<void>(`/api/runs/${runId}/answer`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

// SSE stream URL — direct to backend (not proxied)
export function getSSEUrl(runId: string, streamToken?: string) {
  const base = `${DIRECT_API_BASE}/api/runs/${runId}/stream`;
  if (streamToken) {
    return `${base}?token=${encodeURIComponent(streamToken)}`;
  }
  return base;
}

// Drafts — authenticated via proxy
export function createDraft(data: import("@/types").CreateDraftRequest) {
  return apiFetch<import("@/types").Draft>("/api/drafts", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function listDrafts() {
  return apiFetch<import("@/types").Draft[]>("/api/drafts");
}

export function getDraft(draftId: string) {
  return apiFetch<import("@/types").Draft>(`/api/drafts/${draftId}`);
}

export function updateDraft(
  draftId: string,
  data: import("@/types").UpdateDraftRequest
) {
  return apiFetch<import("@/types").Draft>(`/api/drafts/${draftId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteDraft(draftId: string) {
  return apiFetch<void>(`/api/drafts/${draftId}`, { method: "DELETE" });
}

// LinkedIn — authenticated via proxy
export function getLinkedInAuthUrl() {
  return apiFetch<{ auth_url: string }>("/api/linkedin/auth-url");
}

export function getLinkedInStatus() {
  return apiFetch<import("@/types").LinkedInStatus>("/api/linkedin/status");
}

export function publishToLinkedIn(draftId: string) {
  return apiFetch<import("@/types").PublishResponse>("/api/linkedin/publish", {
    method: "POST",
    body: JSON.stringify({ draft_id: draftId }),
  });
}

export function disconnectLinkedIn() {
  return apiFetch<void>("/api/linkedin/disconnect", { method: "DELETE" });
}

export function listDraftsByStatus(status: string) {
  return apiFetch<import("@/types").Draft[]>(
    `/api/drafts?status=${status}`
  );
}

// Settings — authenticated via proxy
export function getUserSettings() {
  return apiFetch<import("@/types").UserSettings>("/api/settings");
}

export function updateUserSettings(data: import("@/types").UserSettings) {
  return apiFetch<import("@/types").UserSettings>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}
