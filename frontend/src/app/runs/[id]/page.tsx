"use client";

import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { Navbar } from "@/components/navbar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useSSE } from "@/lib/hooks";
import { getRun, getSSEUrl } from "@/lib/api";
import type { RunStatus } from "@/types";

const STAGES: { key: RunStatus; label: string }[] = [
  { key: "ingesting", label: "Ingesting repo data" },
  { key: "analyzing", label: "Analyzing project" },
  { key: "capturing", label: "Capturing screenshots" },
  { key: "generating", label: "Generating post draft" },
  { key: "completed", label: "Complete" },
];

function stageIndex(status: RunStatus): number {
  const idx = STAGES.findIndex((s) => s.key === status);
  return idx === -1 ? -1 : idx;
}

function StepIcon({ state }: { state: "pending" | "active" | "completed" | "failed" }) {
  if (state === "completed") {
    return (
      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-green-500">
        <svg className="h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      </div>
    );
  }
  if (state === "active") {
    return <div className="stepper-active h-6 w-6 rounded-full bg-blue-500" />;
  }
  if (state === "failed") {
    return (
      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-red-500">
        <svg className="h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </div>
    );
  }
  return <div className="h-6 w-6 rounded-full border-2 border-gray-300 dark:border-gray-600" />;
}

export default function RunStatusPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const { events, isDone, error: sseError } = useSSE(getSSEUrl(id));
  const { data: run } = useSWR(`/run/${id}`, () => getRun(id), {
    refreshInterval: 3000,
  });

  const currentStatus: RunStatus = run?.status ?? "pending";
  const isFailed = currentStatus === "failed";
  const isCompleted = isDone || currentStatus === "completed";
  const activeIdx = stageIndex(currentStatus);

  // Derive latest SSE message per stage
  const latestMessages: Record<string, string> = {};
  for (const evt of events) {
    latestMessages[evt.stage] = evt.message;
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <Navbar />
      <main className="mx-auto max-w-xl px-4 py-12">
        <Card header={<h2 className="text-lg font-semibold text-gray-900 dark:text-white">Pipeline Status</h2>}>
          <div className="flex flex-col gap-0">
            {STAGES.map((stage, idx) => {
              let state: "pending" | "active" | "completed" | "failed" = "pending";
              if (isFailed && idx === activeIdx) {
                state = "failed";
              } else if (idx < activeIdx || isCompleted) {
                state = "completed";
              } else if (idx === activeIdx && !isFailed) {
                state = "active";
              }

              return (
                <div key={stage.key}>
                  <div className="flex items-center gap-3 py-2">
                    <StepIcon state={state} />
                    <div>
                      <p className="text-sm font-medium text-gray-900 dark:text-white">
                        {stage.label}
                      </p>
                      {latestMessages[stage.key] && (
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {latestMessages[stage.key]}
                        </p>
                      )}
                    </div>
                  </div>
                  {idx < STAGES.length - 1 && (
                    <div className="ml-[11px] h-4 w-0.5 bg-gray-200 dark:bg-gray-700" />
                  )}
                </div>
              );
            })}
          </div>

          {sseError && (
            <p className="mt-4 text-sm text-yellow-600">{sseError} (using polling fallback)</p>
          )}

          {isFailed && (
            <p className="mt-4 text-sm text-red-600">
              {run?.error ?? "Pipeline failed. Please try again."}
            </p>
          )}

          {isCompleted && (
            <div className="mt-6">
              <Button onClick={() => router.push(`/runs/${id}/review`)}>
                Review Results
              </Button>
            </div>
          )}
        </Card>
      </main>
    </div>
  );
}
