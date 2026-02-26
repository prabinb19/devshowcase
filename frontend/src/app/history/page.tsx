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
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <Navbar />
      <main className="mx-auto max-w-4xl px-4 py-12">
        <h1 className="mb-8 text-2xl font-bold text-gray-900 dark:text-white">
          Published Posts
        </h1>

        {error && (
          <p className="text-center text-red-600">Failed to load history.</p>
        )}

        {!userId && !error && (
          <div className="text-center">
            <p className="text-gray-500 dark:text-gray-400">
              No published posts found. Create and publish a showcase first.
            </p>
            <Link href="/dashboard">
              <Button className="mt-4">Go to Dashboard</Button>
            </Link>
          </div>
        )}

        {userId && !drafts && !error && (
          <p className="text-center text-gray-500">Loading...</p>
        )}

        {drafts && drafts.length === 0 && (
          <div className="text-center">
            <p className="text-gray-500 dark:text-gray-400">
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
                    <span className="inline-block rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                      Published
                    </span>
                    <span className="text-xs text-gray-500">
                      {draft.published_at
                        ? formatDate(draft.published_at)
                        : formatDate(draft.created_at)}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700 dark:text-gray-300">
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
                        className="text-sm font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
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
