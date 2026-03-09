"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Navbar } from "@/components/navbar";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useUser } from "@/lib/hooks";
import { createRun } from "@/lib/api";

const GITHUB_REPO_RE = /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/?$/;

export default function DashboardPage() {
  const user = useUser();
  const router = useRouter();
  const [repoUrl, setRepoUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const trimmed = repoUrl.trim().replace(/\/+$/, "");
    if (!GITHUB_REPO_RE.test(trimmed + "/") && !GITHUB_REPO_RE.test(trimmed)) {
      if (!trimmed.match(/^https:\/\/github\.com\/[^/]+\/[^/]+$/)) {
        setError("URL must match https://github.com/{owner}/{repo}");
        return;
      }
    }

    if (!user) {
      setError("Not signed in");
      return;
    }

    setLoading(true);
    try {
      const data = await createRun(trimmed);
      router.push(`/runs/${data.run_id}?st=${encodeURIComponent(data.stream_token)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create run");
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-win98-silver">
      <Navbar />
      <main className="mx-auto max-w-2xl px-4 py-12">
        <Card header={<h2 className="text-lg font-semibold text-white">New Showcase</h2>}>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <Input
              label="Repository URL"
              placeholder="https://github.com/owner/repo"
              value={repoUrl}
              onChange={(e) => {
                setRepoUrl(e.target.value);
                setError(null);
              }}
              error={error ?? undefined}
            />
            <Button type="submit" loading={loading}>
              Analyze Repository
            </Button>
          </form>
        </Card>
      </main>
    </div>
  );
}
