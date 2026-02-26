"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Image from "next/image";
import useSWR from "swr";
import { Navbar } from "@/components/navbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useUser } from "@/lib/hooks";
import { getRun, regenerateRun, createDraft } from "@/lib/api";

export default function ReviewPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const user = useUser();

  const { data: run, error: fetchError } = useSWR(`/run/${id}`, () => getRun(id));

  const [body, setBody] = useState<string | null>(null);
  const [firstComment, setFirstComment] = useState<string | null>(null);
  const [selectedScreenshots, setSelectedScreenshots] = useState<Set<number>>(new Set());
  const [altTexts, setAltTexts] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [feedback, setFeedback] = useState("");

  // Initialize state from run data once loaded
  const draft = run?.post_draft;
  const displayBody = body ?? draft?.body ?? "";
  const displayComment = firstComment ?? draft?.first_comment ?? "";
  const displayAltTexts = altTexts.length > 0 ? altTexts : draft?.alt_texts ?? [];

  // Initialize selections on first load
  if (draft && body === null) {
    // Use setTimeout-free approach: set state will be picked up next render
    // We use the ?? pattern above instead
  }
  if (draft && selectedScreenshots.size === 0 && draft.screenshot_urls.length > 0 && body === null) {
    // Select all screenshots by default on first render
    const allSelected = new Set(draft.screenshot_urls.map((_, i) => i));
    if (allSelected.size > 0 && selectedScreenshots.size === 0) {
      // This runs once effectively
      setTimeout(() => {
        setSelectedScreenshots(allSelected);
        setAltTexts(draft.alt_texts ?? draft.screenshot_urls.map(() => ""));
      }, 0);
    }
  }

  const charCount = displayBody.length;

  function toggleScreenshot(idx: number) {
    setSelectedScreenshots((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      return next;
    });
  }

  function updateAltText(idx: number, value: string) {
    setAltTexts((prev) => {
      const next = [...(prev.length > 0 ? prev : draft?.alt_texts ?? [])];
      next[idx] = value;
      return next;
    });
  }

  async function handleSaveDraft() {
    if (!run || !user) return;

    // Store user UUID for drafts page
    if (typeof window !== "undefined") {
      localStorage.setItem("devshowcase_user_id", run.user_id);
    }

    setSaving(true);
    try {
      const selectedUrls = draft?.screenshot_urls.filter((_, i) => selectedScreenshots.has(i)) ?? [];
      const selectedAlts = displayAltTexts.filter((_, i) => selectedScreenshots.has(i));

      await createDraft({
        run_id: run.id,
        user_id: run.user_id,
        body: displayBody,
        first_comment: displayComment || undefined,
        screenshot_urls: selectedUrls.length > 0 ? selectedUrls : undefined,
        alt_texts: selectedAlts.length > 0 ? selectedAlts : undefined,
      });
      router.push("/drafts");
    } catch {
      setSaving(false);
    }
  }

  async function handleRegenerate() {
    if (!feedback.trim()) return;
    setRegenerating(true);
    try {
      const data = await regenerateRun(id, feedback.trim());
      router.push(`/runs/${data.run_id}`);
    } catch {
      setRegenerating(false);
    }
  }

  function handleDiscard() {
    if (window.confirm("Discard this draft and return to dashboard?")) {
      router.push("/dashboard");
    }
  }

  if (fetchError) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
        <Navbar />
        <main className="mx-auto max-w-5xl px-4 py-12">
          <p className="text-center text-red-600">Failed to load run details.</p>
        </main>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
        <Navbar />
        <main className="mx-auto max-w-5xl px-4 py-12">
          <p className="text-center text-gray-500">Loading...</p>
        </main>
      </div>
    );
  }

  if (!draft) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
        <Navbar />
        <main className="mx-auto max-w-5xl px-4 py-12">
          <p className="text-center text-gray-500">No post draft available for this run.</p>
        </main>
      </div>
    );
  }

  const selectedUrls = draft.screenshot_urls.filter((_, i) => selectedScreenshots.has(i));

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <Navbar />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <div className="grid gap-8 lg:grid-cols-2">
          {/* Left Column - Editor */}
          <div className="flex flex-col gap-6">
            <Card header={<h2 className="text-lg font-semibold text-gray-900 dark:text-white">Edit Post</h2>}>
              <div className="flex flex-col gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Post Body
                  </label>
                  <textarea
                    rows={8}
                    className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
                    value={displayBody}
                    onChange={(e) => setBody(e.target.value)}
                  />
                  <p
                    className={`mt-1 text-xs ${
                      charCount >= 3000
                        ? "text-red-600"
                        : charCount >= 2700
                          ? "text-yellow-600"
                          : "text-gray-500"
                    }`}
                  >
                    {charCount}/3000
                  </p>
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                    First Comment
                  </label>
                  <textarea
                    rows={3}
                    className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
                    value={displayComment}
                    onChange={(e) => setFirstComment(e.target.value)}
                  />
                </div>

                {draft.screenshot_urls.length > 0 && (
                  <div>
                    <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300">
                      Screenshots
                    </label>
                    <div className="grid gap-4 sm:grid-cols-2">
                      {draft.screenshot_urls.map((url, idx) => (
                        <div key={idx} className="flex flex-col gap-2 rounded-lg border border-gray-200 p-3 dark:border-gray-700">
                          <label className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={selectedScreenshots.has(idx)}
                              onChange={() => toggleScreenshot(idx)}
                              className="rounded"
                            />
                            <span className="text-xs text-gray-500">Include</span>
                          </label>
                          <div className="relative aspect-video w-full overflow-hidden rounded">
                            <Image
                              src={url}
                              alt={displayAltTexts[idx] ?? `Screenshot ${idx + 1}`}
                              fill
                              className="object-cover"
                            />
                          </div>
                          <input
                            type="text"
                            placeholder="Alt text"
                            className="w-full rounded border border-gray-300 px-2 py-1 text-xs dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
                            value={displayAltTexts[idx] ?? ""}
                            onChange={(e) => updateAltText(idx, e.target.value)}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </Card>
          </div>

          {/* Right Column - Preview */}
          <div>
            <Card header={<h2 className="text-lg font-semibold text-gray-900 dark:text-white">LinkedIn Preview</h2>}>
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-3">
                  {user?.image && (
                    <Image
                      src={user.image}
                      alt={user.name ?? "Avatar"}
                      width={40}
                      height={40}
                      className="rounded-full"
                    />
                  )}
                  <div>
                    <p className="text-sm font-semibold text-gray-900 dark:text-white">
                      {user?.name ?? user?.githubUsername ?? "You"}
                    </p>
                    <p className="text-xs text-gray-500">Just now</p>
                  </div>
                </div>

                <p className="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-200">
                  {displayBody}
                </p>

                {selectedUrls.length > 0 && (
                  <div className="relative aspect-video w-full overflow-hidden rounded-lg">
                    <Image
                      src={selectedUrls[0]}
                      alt="Post image"
                      fill
                      className="object-cover"
                    />
                  </div>
                )}

                <div className="flex justify-between border-t border-gray-200 pt-3 dark:border-gray-700">
                  {["Like", "Comment", "Repost", "Send"].map((action) => (
                    <span key={action} className="text-xs text-gray-500">
                      {action}
                    </span>
                  ))}
                </div>
              </div>
            </Card>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="mt-8 flex flex-wrap gap-3">
          <Button variant="secondary" onClick={() => setShowFeedbackModal(true)}>
            Regenerate with Feedback
          </Button>
          <Button loading={saving} onClick={handleSaveDraft}>
            Save as Draft
          </Button>
          <Button variant="ghost" onClick={handleDiscard}>
            Discard
          </Button>
        </div>

        {/* Feedback Modal */}
        {showFeedbackModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="mx-4 w-full max-w-md rounded-xl bg-white p-6 shadow-lg dark:bg-gray-900">
              <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
                Regeneration Feedback
              </h3>
              <textarea
                rows={4}
                className="mb-4 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
                placeholder="What should be different in the next version?"
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
              />
              <div className="flex justify-end gap-3">
                <Button variant="ghost" onClick={() => setShowFeedbackModal(false)}>
                  Cancel
                </Button>
                <Button loading={regenerating} onClick={handleRegenerate}>
                  Submit
                </Button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
