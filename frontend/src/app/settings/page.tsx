"use client";

import { useState } from "react";
import useSWR from "swr";
import { Navbar } from "@/components/navbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useUser } from "@/lib/hooks";
import {
  getUserSettings,
  updateUserSettings,
  getLinkedInStatus,
  getLinkedInAuthUrl,
  disconnectLinkedIn,
} from "@/lib/api";
import type { ToneOption } from "@/types";

const TONE_OPTIONS: { value: ToneOption; label: string }[] = [
  { value: "professional", label: "Professional" },
  { value: "casual", label: "Casual" },
  { value: "technical", label: "Technical" },
  { value: "enthusiastic", label: "Enthusiastic" },
];

export default function SettingsPage() {
  const user = useUser();

  const { data: settings, mutate: mutateSettings } = useSWR(
    user ? `settings-${user.githubId}` : null,
    () => getUserSettings(user!.githubId, user!.githubUsername)
  );

  const { data: linkedInStatus, mutate: mutateLinkedIn } = useSWR(
    user ? `linkedin-status-${user.githubId}` : null,
    () => getLinkedInStatus(user!.githubId, user!.githubUsername)
  );

  const [tone, setTone] = useState<ToneOption | null>(null);
  const [hashtagInput, setHashtagInput] = useState("");
  const [hashtags, setHashtags] = useState<string[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const displayTone = tone ?? settings?.default_tone ?? "professional";
  const displayHashtags = hashtags ?? settings?.hashtags ?? [];

  function addHashtag() {
    const tag = hashtagInput.trim().replace(/^#/, "");
    if (!tag) return;
    if (displayHashtags.includes(tag)) {
      setHashtagInput("");
      return;
    }
    const updated = [...displayHashtags, tag];
    setHashtags(updated);
    setHashtagInput("");
  }

  function removeHashtag(idx: number) {
    const updated = displayHashtags.filter((_, i) => i !== idx);
    setHashtags(updated);
  }

  async function handleSave() {
    if (!user) return;
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await updateUserSettings(user.githubId, user.githubUsername, {
        default_tone: displayTone,
        hashtags: displayHashtags,
      });
      mutateSettings();
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setError("Failed to save preferences. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  async function handleConnectLinkedIn() {
    setError(null);
    try {
      const { auth_url } = await getLinkedInAuthUrl();
      window.location.href = auth_url;
    } catch {
      setError("Failed to connect LinkedIn. Please try again.");
    }
  }

  async function handleDisconnectLinkedIn() {
    if (!user) return;
    if (!window.confirm("Disconnect your LinkedIn account?")) return;
    setDisconnecting(true);
    setError(null);
    try {
      await disconnectLinkedIn(user.githubId, user.githubUsername);
      mutateLinkedIn();
    } catch {
      setError("Failed to disconnect LinkedIn. Please try again.");
    } finally {
      setDisconnecting(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <Navbar />
      <main className="mx-auto max-w-2xl px-4 py-12">
        <h1 className="mb-8 text-2xl font-bold text-gray-900 dark:text-white">
          Settings
        </h1>

        {error && (
          <p className="mb-4 text-sm text-red-600">{error}</p>
        )}

        {/* Post Preferences */}
        <Card
          header={
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Post Preferences
            </h2>
          }
          className="mb-6"
        >
          <div className="flex flex-col gap-5">
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300">
                Default Tone
              </label>
              <div className="flex flex-wrap gap-2">
                {TONE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setTone(opt.value)}
                    className={`rounded-lg border px-3 py-1.5 text-sm transition-colors ${
                      displayTone === opt.value
                        ? "border-blue-500 bg-blue-50 text-blue-700 dark:border-blue-400 dark:bg-blue-900/30 dark:text-blue-300"
                        : "border-gray-300 text-gray-600 hover:border-gray-400 dark:border-gray-600 dark:text-gray-400 dark:hover:border-gray-500"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300">
                Default Hashtags
              </label>
              {displayHashtags.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-1.5">
                  {displayHashtags.map((tag, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-700 dark:bg-gray-800 dark:text-gray-300"
                    >
                      #{tag}
                      <button
                        onClick={() => removeHashtag(idx)}
                        className="ml-0.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                      >
                        x
                      </button>
                    </span>
                  ))}
                </div>
              )}
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Add hashtag..."
                  className="flex-1 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
                  value={hashtagInput}
                  onChange={(e) => setHashtagInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addHashtag();
                    }
                  }}
                />
                <Button variant="secondary" onClick={addHashtag}>
                  Add
                </Button>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Button loading={saving} onClick={handleSave}>
                Save Preferences
              </Button>
              {saved && (
                <span className="text-sm text-green-600 dark:text-green-400">
                  Saved!
                </span>
              )}
            </div>
          </div>
        </Card>

        {/* LinkedIn Connection */}
        <Card
          header={
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              LinkedIn Connection
            </h2>
          }
        >
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <div
                className={`h-2.5 w-2.5 rounded-full ${
                  linkedInStatus?.connected
                    ? "bg-green-500"
                    : "bg-gray-300 dark:bg-gray-600"
                }`}
              />
              <span className="text-sm text-gray-700 dark:text-gray-300">
                {linkedInStatus?.connected
                  ? "Connected"
                  : "Not connected"}
              </span>
              {linkedInStatus?.expires_at && (
                <span className="text-xs text-gray-500">
                  Expires{" "}
                  {new Date(linkedInStatus.expires_at).toLocaleDateString()}
                </span>
              )}
            </div>
            {linkedInStatus?.connected ? (
              <Button
                variant="danger"
                loading={disconnecting}
                onClick={handleDisconnectLinkedIn}
                className="w-fit"
              >
                Disconnect LinkedIn
              </Button>
            ) : (
              <Button onClick={handleConnectLinkedIn} className="w-fit">
                Connect LinkedIn
              </Button>
            )}
          </div>
        </Card>
      </main>
    </div>
  );
}
