"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { Navbar } from "@/components/navbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useUser } from "@/lib/hooks";
import { listDraftsByStatus } from "@/lib/api";
import type { Draft } from "@/types";

export default function HistoryPage() {
  useUser();
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("devshowcase_user_id");
      if (stored) setUserId(stored);
    }
  }, []);

  const { data: drafts, error } = useSWR(
    userId ? `history-${userId}` : null,
    () => listDraftsByStatus(userId!, "published")
  );

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
        <h1 className="mb-8 text-2xl font-bold uppercase text-win98-black">
          Published Posts
        </h1>

        {error && (
          <p className="text-center text-win98-red font-bold">Failed to load history.</p>
        )}

        {!userId && !error && (
          <div className="text-center">
            <p className="text-win98-black">
              No published posts found. Create and publish a showcase first.
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
            <p className="text-win98-black">
              No published posts yet.
            </p>
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
                    <span className="inline-block bg-win98-navy text-white bevel-outset px-2 py-0.5 text-xs font-bold uppercase">
                      Published
                    </span>
                    <span className="text-xs text-win98-darkgray font-bold">
                      {draft.published_at
                        ? formatDate(draft.published_at)
                        : formatDate(draft.created_at)}
                    </span>
                  </div>
                  <p className="text-sm text-win98-black">
                    {draft.body.length > 120
                      ? draft.body.slice(0, 120) + "..."
                      : draft.body}
                  </p>
                  {draft.published_url && (
                    <div className="flex justify-end">
                      <a
                        href={draft.published_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-bold text-win98-blue hover:text-win98-red"
                      >
                        View on LinkedIn
                      </a>
                    </div>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
