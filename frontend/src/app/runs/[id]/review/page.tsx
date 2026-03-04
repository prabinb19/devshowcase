"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Image from "next/image";
import useSWR from "swr";
import { Navbar } from "@/components/navbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useUser } from "@/lib/hooks";
import {
  getRun,
  createDraft,
  getLinkedInStatus,
  getLinkedInAuthUrl,
  publishToLinkedIn,
} from "@/lib/api";

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
  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Initialize state from run data once loaded
  const draft = run?.post_draft ?? run?.agent_output?.post_draft ?? null;
  const displayBody = body ?? draft?.body ?? "";
  const displayComment = firstComment ?? draft?.first_comment ?? "";
  const displayAltTexts = altTexts.length > 0 ? altTexts : draft?.alt_texts ?? [];

  // Initialize selections when draft data arrives
  useEffect(() => {
    if (!draft) return;
    if (draft.screenshot_urls.length > 0) {
      setSelectedScreenshots(new Set(draft.screenshot_urls.map((_: string, i: number) => i)));
      setAltTexts(draft.alt_texts ?? draft.screenshot_urls.map(() => ""));
    }
  }, [draft]);

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
    setError(null);
    try {
      const selectedUrls = draft?.screenshot_urls.filter((_: string, i: number) => selectedScreenshots.has(i)) ?? [];
      const selectedAlts = displayAltTexts.filter((_: string, i: number) => selectedScreenshots.has(i));

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
      setError("Failed to save draft. Please try again.");
      setSaving(false);
    }
  }

  async function handlePublish() {
    if (!run || !user) return;

    // Store user UUID
    if (typeof window !== "undefined") {
      localStorage.setItem("devshowcase_user_id", run.user_id);
    }

    setPublishing(true);
    setPublishError(null);

    try {
      // Check LinkedIn connection status
      const status = await getLinkedInStatus(user.githubId, user.githubUsername);
      if (!status.connected) {
        // Redirect to LinkedIn OAuth
        const { auth_url } = await getLinkedInAuthUrl();
        window.location.href = auth_url;
        return;
      }

      // Save as draft first
      const selectedUrls = draft?.screenshot_urls.filter((_: string, i: number) => selectedScreenshots.has(i)) ?? [];
      const selectedAlts = displayAltTexts.filter((_: string, i: number) => selectedScreenshots.has(i));

      const savedDraft = await createDraft({
        run_id: run.id,
        user_id: run.user_id,
        body: displayBody,
        first_comment: displayComment || undefined,
        screenshot_urls: selectedUrls.length > 0 ? selectedUrls : undefined,
        alt_texts: selectedAlts.length > 0 ? selectedAlts : undefined,
      });

      // Publish the draft
      const result = await publishToLinkedIn(
        savedDraft.id,
        user.githubId,
        user.githubUsername
      );

      if (result.success) {
        router.push("/history");
      } else {
        setPublishError(result.error ?? "Publishing failed");
        setPublishing(false);
      }
    } catch {
      setPublishError("Failed to publish. Please try again.");
      setPublishing(false);
    }
  }

  function handleDiscard() {
    if (window.confirm("Discard this draft and return to dashboard?")) {
      router.push("/dashboard");
    }
  }

  if (fetchError) {
    return (
      <div className="min-h-screen bg-win98-silver">
        <Navbar />
        <main className="mx-auto max-w-5xl px-4 py-12">
          <p className="text-center text-win98-red font-bold">Failed to load run details.</p>
        </main>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="min-h-screen bg-win98-silver">
        <Navbar />
        <main className="mx-auto max-w-5xl px-4 py-12">
          <p className="text-center text-win98-black">Loading...</p>
        </main>
      </div>
    );
  }

  if (!draft) {
    return (
      <div className="min-h-screen bg-win98-silver">
        <Navbar />
        <main className="mx-auto max-w-5xl px-4 py-12">
          <p className="text-center text-win98-black">No post draft available for this run.</p>
        </main>
      </div>
    );
  }

  const selectedUrls = draft.screenshot_urls.filter((_: string, i: number) => selectedScreenshots.has(i));

  return (
    <div className="min-h-screen bg-win98-silver">
      <Navbar />
      <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8">
        <div className="grid gap-6 sm:gap-8 lg:grid-cols-2">
          {/* Left Column - Editor */}
          <div className="flex flex-col gap-6">
            <Card header={<h2 className="text-lg font-semibold text-white">Edit Post</h2>}>
              <div className="flex flex-col gap-4">
                <div>
                  <label className="mb-1 block text-sm font-bold text-win98-black">
                    Post Body
                  </label>
                  <textarea
                    rows={8}
                    className="w-full bevel-inset bg-white px-3 py-2 text-sm text-win98-black focus:outline-dotted focus:outline-2 focus:outline-win98-black"
                    value={displayBody}
                    onChange={(e) => setBody(e.target.value)}
                  />
                  <p
                    className={`mt-1 text-xs font-bold ${
                      charCount >= 3000
                        ? "text-win98-red"
                        : charCount >= 2700
                          ? "text-win98-yellow"
                          : "text-win98-darkgray"
                    }`}
                  >
                    {charCount}/3000
                  </p>
                </div>

                <div>
                  <label className="mb-1 block text-sm font-bold text-win98-black">
                    First Comment
                  </label>
                  <textarea
                    rows={3}
                    className="w-full bevel-inset bg-white px-3 py-2 text-sm text-win98-black focus:outline-dotted focus:outline-2 focus:outline-win98-black"
                    value={displayComment}
                    onChange={(e) => setFirstComment(e.target.value)}
                  />
                </div>

                {draft.screenshot_urls.length > 0 && (
                  <div>
                    <label className="mb-2 block text-sm font-bold text-win98-black">
                      Screenshots
                    </label>
                    <div className="grid gap-3 grid-cols-1 sm:grid-cols-2">
                      {draft.screenshot_urls.map((url: string, idx: number) => (
                        <div key={idx} className="flex flex-col gap-2 bevel-inset p-2 sm:p-3">
                          <label className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={selectedScreenshots.has(idx)}
                              onChange={() => toggleScreenshot(idx)}
                            />
                            <span className="text-xs text-win98-black font-bold">Include</span>
                          </label>
                          <div className="relative aspect-video w-full overflow-hidden">
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
                            className="w-full bevel-inset bg-white px-2 py-1 text-xs text-win98-black"
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
            <Card header={<h2 className="text-lg font-semibold text-white">LinkedIn Preview</h2>}>
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-3">
                  {user?.image && (
                    <div className="bevel-inset p-0.5">
                      <Image
                        src={user.image}
                        alt={user.name ?? "Avatar"}
                        width={40}
                        height={40}
                      />
                    </div>
                  )}
                  <div>
                    <p className="text-sm font-bold text-win98-black">
                      {user?.name ?? user?.githubUsername ?? "You"}
                    </p>
                    <p className="text-xs text-win98-darkgray">Just now</p>
                  </div>
                </div>

                <p className="whitespace-pre-wrap text-sm text-win98-black">
                  {displayBody}
                </p>

                {selectedUrls.length > 0 && (
                  <div className="relative aspect-video w-full overflow-hidden bevel-inset">
                    <Image
                      src={selectedUrls[0]}
                      alt="Post image"
                      fill
                      className="object-cover"
                    />
                  </div>
                )}

                <div className="flex justify-between groove-hr pt-3">
                  {["Like", "Comment", "Repost", "Send"].map((action) => (
                    <span key={action} className="text-xs text-win98-darkgray uppercase font-bold">
                      {action}
                    </span>
                  ))}
                </div>
              </div>
            </Card>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="mt-6 flex flex-col gap-3 sm:mt-8">
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:gap-3">
            <Button loading={publishing} onClick={handlePublish}>
              Publish to LinkedIn
            </Button>
            <Button variant="secondary" loading={saving} onClick={handleSaveDraft}>
              Save as Draft
            </Button>
            <Button variant="ghost" onClick={handleDiscard}>
              Discard
            </Button>
          </div>
          {(error || publishError) && (
            <p className="text-sm text-win98-red font-bold">{error || publishError}</p>
          )}
          {run?.agent_output?.portfolio_pr_url && (
            <a
              href={run.agent_output.portfolio_pr_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-win98-blue hover:text-win98-red"
            >
              View Portfolio PR
            </a>
          )}
        </div>
      </main>
    </div>
  );
}
