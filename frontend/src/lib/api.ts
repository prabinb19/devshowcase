const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${path}`;
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

// Runs
export function createRun(
  repoUrl: string,
  githubId: string,
  githubUsername: string
) {
  return apiFetch<{ run_id: string; status: string }>("/api/runs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-GitHub-Id": githubId,
      "X-GitHub-Username": githubUsername,
    },
    body: JSON.stringify({ repo_url: repoUrl }),
  });
}

export function getRun(runId: string) {
  return apiFetch<import("@/types").RunDetail>(`/api/runs/${runId}`);
}

export function regenerateRun(runId: string, feedback: string) {
  return apiFetch<{ run_id: string; status: string }>(
    `/api/runs/${runId}/regenerate`,
    {
      method: "POST",
      body: JSON.stringify({ feedback }),
    }
  );
}

export function getSSEUrl(runId: string) {
  return `${API_BASE}/api/runs/${runId}/stream`;
}

// Drafts
export function createDraft(data: import("@/types").CreateDraftRequest) {
  return apiFetch<import("@/types").Draft>("/api/drafts", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function listDrafts(userId: string) {
  return apiFetch<import("@/types").Draft[]>(`/api/drafts?user_id=${userId}`);
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

// LinkedIn
export function getLinkedInAuthUrl() {
  return apiFetch<{ auth_url: string }>("/api/linkedin/auth-url");
}

export function getLinkedInStatus(githubId: string, githubUsername: string) {
  return apiFetch<import("@/types").LinkedInStatus>("/api/linkedin/status", {
    headers: {
      "X-GitHub-Id": githubId,
      "X-GitHub-Username": githubUsername,
    },
  });
}

export function publishToLinkedIn(
  draftId: string,
  githubId: string,
  githubUsername: string
) {
  return apiFetch<import("@/types").PublishResponse>("/api/linkedin/publish", {
    method: "POST",
    headers: {
      "X-GitHub-Id": githubId,
      "X-GitHub-Username": githubUsername,
    },
    body: JSON.stringify({ draft_id: draftId }),
  });
}

export function disconnectLinkedIn(githubId: string, githubUsername: string) {
  return apiFetch<void>("/api/linkedin/disconnect", {
    method: "DELETE",
    headers: {
      "X-GitHub-Id": githubId,
      "X-GitHub-Username": githubUsername,
    },
  });
}

export function listDraftsByStatus(userId: string, status: string) {
  return apiFetch<import("@/types").Draft[]>(
    `/api/drafts?user_id=${userId}&status=${status}`
  );
}
