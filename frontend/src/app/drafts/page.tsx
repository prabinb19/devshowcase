"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { Navbar } from "@/components/navbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useUser } from "@/lib/hooks";
import { listDrafts, deleteDraft } from "@/lib/api";
import type { Draft, DraftStatus } from "@/types";

const STATUS_COLORS: Record<DraftStatus, string> = {
  draft: "bg-win98-green text-white bevel-outset",
  published: "bg-win98-navy text-white bevel-outset",
  archived: "bg-win98-darkgray text-white bevel-outset",
};

export default function DraftsPage() {
  useUser(); // ensure session is active
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("devshowcase_user_id");
      if (stored) setUserId(stored);
    }
  }, []);

  const { data: drafts, error, mutate } = useSWR(
    userId ? `drafts-${userId}` : null,
    () => listDrafts()
  );

  async function handleDelete(draftId: string) {
    if (!window.confirm("Delete this draft?")) return;
    await deleteDraft(draftId);
    mutate();
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  return (
    <div className="min-h-screen bg-win98-silver">
      <Navbar />
      <main className="mx-auto max-w-4xl px-4 py-12">
        <h1 className="mb-8 text-2xl font-bold uppercase text-win98-black">Your Drafts</h1>

        {error && (
          <p className="text-center text-win98-red font-bold">Failed to load drafts.</p>
        )}

        {!userId && !error && (
          <div className="text-center">
            <p className="text-win98-black">
              No drafts found. Create a showcase first to see your drafts here.
            </p>
            <Link href="/dashboard">
              <Button className="mt-4">Go to Dashboard</Button>
            </Link>
          </div>
        )}

        {userId && !drafts && !error && (
          <p className="text-center text-win98-black">Loading...</p>
        )}

        {drafts && drafts.length === 0 && (
          <div className="text-center">
            <p className="text-win98-black">No drafts yet.</p>
            <Link href="/dashboard">
              <Button className="mt-4">Go to Dashboard</Button>
            </Link>
          </div>
        )}

        {drafts && drafts.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2">
            {drafts.map((draft: Draft) => (
              <Card key={draft.id}>
                <div className="flex flex-col gap-3">
                  <div className="flex items-start justify-between">
                    <span
                      className={`inline-block px-2 py-0.5 text-xs font-bold uppercase ${STATUS_COLORS[draft.status]}`}
                    >
                      {draft.status}
                    </span>
                    <span className="text-xs text-win98-darkgray font-bold">
                      {formatDate(draft.created_at)}
                    </span>
                  </div>
                  <p className="text-sm text-win98-black">
                    {draft.body.length > 120
                      ? draft.body.slice(0, 120) + "..."
                      : draft.body}
                  </p>
                  <div className="flex justify-end">
                    <Button
                      variant="danger"
                      className="text-xs"
                      onClick={() => handleDelete(draft.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
