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
  getDraft,
  updateDraft,
  getLinkedInStatus,
  getLinkedInAuthUrl,
  publishToLinkedIn,
} from "@/lib/api";

export default function DraftEditPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const user = useUser();

  const { data: draft, error: fetchError } = useSWR(`/drafts/${id}`, () => getDraft(id));

  const [body, setBody] = useState<string | null>(null);
  const [firstComment, setFirstComment] = useState<string | null>(null);
  const [selectedScreenshots, setSelectedScreenshots] = useState<Set<number>>(new Set());
  const [altTexts, setAltTexts] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const displayBody = body ?? draft?.body ?? "";
  const displayComment = firstComment ?? draft?.first_comment ?? "";
  const screenshotUrls = draft?.screenshot_urls ?? [];
  const displayAltTexts = altTexts.length > 0 ? altTexts : draft?.alt_texts ?? [];

  // Initialize selections when draft data arrives
  useEffect(() => {
    if (!draft) return;
    if (screenshotUrls.length > 0) {
      setSelectedScreenshots(new Set(screenshotUrls.map((_: string, i: number) => i)));
      setAltTexts(draft.alt_texts ?? screenshotUrls.map(() => ""));
    }
  }, [draft]); // eslint-disable-line react-hooks/exhaustive-deps

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

  async function handleSave() {
    if (!draft) return;

    setSaving(true);
    setError(null);
    try {
      const selectedUrls = screenshotUrls.filter((_: string, i: number) => selectedScreenshots.has(i));
      const selectedAlts = displayAltTexts.filter((_: string, i: number) => selectedScreenshots.has(i));

      await updateDraft(draft.id, {
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
    if (!draft) return;

    setPublishing(true);
    setPublishError(null);

    try {
      // Check LinkedIn connection status
      const status = await getLinkedInStatus();
      if (!status.connected) {
        const { auth_url } = await getLinkedInAuthUrl();
        window.location.href = auth_url;
        return;
      }

      // Save draft first, then publish
      const selectedUrls = screenshotUrls.filter((_: string, i: number) => selectedScreenshots.has(i));
      const selectedAlts = displayAltTexts.filter((_: string, i: number) => selectedScreenshots.has(i));

      await updateDraft(draft.id, {
        body: displayBody,
        first_comment: displayComment || undefined,
        screenshot_urls: selectedUrls.length > 0 ? selectedUrls : undefined,
        alt_texts: selectedAlts.length > 0 ? selectedAlts : undefined,
      });

      const result = await publishToLinkedIn(draft.id);

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
    if (window.confirm("Discard changes and return to drafts?")) {
      router.push("/drafts");
    }
  }

  if (fetchError) {
    return (
      <div className="min-h-screen bg-win98-silver">
        <Navbar />
        <main className="mx-auto max-w-5xl px-4 py-12">
          <p className="text-center text-win98-red font-bold">Failed to load draft.</p>
        </main>
      </div>
    );
  }

  if (!draft) {
    return (
      <div className="min-h-screen bg-win98-silver">
        <Navbar />
        <main className="mx-auto max-w-5xl px-4 py-12">
          <p className="text-center text-win98-black">Loading...</p>
        </main>
      </div>
    );
  }

  const selectedUrls = screenshotUrls.filter((_: string, i: number) => selectedScreenshots.has(i));

  return (
    <div className="min-h-screen bg-win98-silver">
      <Navbar />
      <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8">
        <div className="grid gap-6 sm:gap-8 lg:grid-cols-2">
          {/* Left Column - Editor */}
          <div className="flex flex-col gap-6">
            <Card header={<h2 className="text-lg font-semibold text-white">Edit Draft</h2>}>
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

                {screenshotUrls.length > 0 && (
                  <div>
                    <label className="mb-2 block text-sm font-bold text-win98-black">
                      Screenshots
                    </label>
                    <div className="grid gap-3 grid-cols-1 sm:grid-cols-2">
                      {screenshotUrls.map((url: string, idx: number) => (
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
          <div className="flex flex-col gap-4">
            {/* AI Transparency Disclosure */}
            <div className="flex items-start gap-2 bevel-outset bg-win98-silver px-3 py-2">
              <span className="text-sm leading-5">*</span>
              <p className="text-xs text-win98-black">
                <span className="font-bold">AI-Generated Content</span> — This draft was created
                by an AI model analyzing the repository. Review and edit before publishing.
                Per{" "}
                <a
                  href="https://www.microsoft.com/en-us/ai/principles-and-approach"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-win98-blue hover:text-win98-red underline"
                >
                  Microsoft Responsible AI
                </a>{" "}
                transparency principles, AI-assisted content should be disclosed.
              </p>
            </div>

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
            <Button variant="secondary" loading={saving} onClick={handleSave}>
              Save Draft
            </Button>
            <Button variant="ghost" onClick={handleDiscard}>
              Discard
            </Button>
          </div>
          {(error || publishError) && (
            <p className="text-sm text-win98-red font-bold">{error || publishError}</p>
          )}
        </div>
      </main>
    </div>
  );
}
