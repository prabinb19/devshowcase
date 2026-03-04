"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { Navbar } from "@/components/navbar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useSSE } from "@/lib/hooks";
import { getRun, getSSEUrl, answerAgentQuestion } from "@/lib/api";
import type { RunStatus, AgentQuestion } from "@/types";

const STAGES: { key: string; label: string }[] = [
  { key: "agent_starting", label: "Starting secure sandbox" },
  { key: "agent_exploring", label: "Exploring repository" },
  { key: "agent_generating", label: "Generating LinkedIn post" },
  { key: "agent_updating_portfolio", label: "Updating portfolio" },
  { key: "completed", label: "Complete" },
];

const STATUS_TO_STAGE: Record<string, string> = {
  pending: "agent_starting",
  agent_starting: "agent_starting",
  agent_exploring: "agent_exploring",
  agent_generating: "agent_generating",
  agent_awaiting_answer: "agent_generating",
  agent_updating_portfolio: "agent_updating_portfolio",
  completed: "completed",
  failed: "failed",
};

function stageIndex(status: RunStatus): number {
  const mapped = STATUS_TO_STAGE[status] ?? status;
  const idx = STAGES.findIndex((s) => s.key === mapped);
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

function QuestionDialog({
  question,
  runId,
  onAnswered,
}: {
  question: AgentQuestion;
  runId: string;
  onAnswered: () => void;
}) {
  const [answer, setAnswer] = useState("");
  const [sending, setSending] = useState(false);

  async function handleSubmit(text: string) {
    setSending(true);
    try {
      await answerAgentQuestion(runId, text);
      onAnswered();
    } catch {
      setSending(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 w-full max-w-md rounded-xl bg-white p-6 shadow-lg dark:bg-gray-900">
        <h3 className="mb-2 text-lg font-semibold text-gray-900 dark:text-white">
          Agent Question
        </h3>
        <p className="mb-4 text-sm text-gray-700 dark:text-gray-300">{question.text}</p>

        {question.options && question.options.length > 0 ? (
          <div className="flex flex-col gap-2">
            {question.options.map((opt) => (
              <Button
                key={opt}
                variant="secondary"
                loading={sending}
                onClick={() => handleSubmit(opt)}
                className="justify-start text-left"
              >
                {opt}
              </Button>
            ))}
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <textarea
              rows={3}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
              placeholder="Type your answer..."
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
            />
            <Button loading={sending} onClick={() => handleSubmit(answer)} disabled={!answer.trim()}>
              Send Answer
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function RunStatusPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const { events, isDone, error: sseError, streamUrl, pendingQuestion, clearQuestion } = useSSE(getSSEUrl(id));
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
        <Card header={<h2 className="text-lg font-semibold text-gray-900 dark:text-white">Agent Status</h2>}>
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
            <div className="mt-4">
              <p className="text-sm text-red-600">
                {run?.error ?? "Agent failed. Please try again."}
              </p>
              <Button
                variant="secondary"
                className="mt-3"
                onClick={() => router.push("/dashboard")}
              >
                Try Another Repo
              </Button>
            </div>
          )}

          {isCompleted && (
            <div className="mt-6">
              <Button onClick={() => router.push(`/runs/${id}/review`)}>
                Review Results
              </Button>
            </div>
          )}
        </Card>

        {streamUrl && !isCompleted && !isFailed && (
          <Card
            header={
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Live Sandbox View
                </h2>
              </div>
            }
            className="mt-6"
          >
            <div className="relative w-full overflow-hidden rounded-lg" style={{ aspectRatio: "16/10" }}>
              <iframe
                src={streamUrl}
                className="absolute inset-0 h-full w-full border-0"
                allow="autoplay"
                sandbox="allow-scripts allow-same-origin"
                title="Agent sandbox live stream"
              />
            </div>
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              Watching the AI agent work in real time. View only.
            </p>
          </Card>
        )}
      </main>

      {pendingQuestion && (
        <QuestionDialog
          question={pendingQuestion}
          runId={id}
          onAnswered={clearQuestion}
        />
      )}
    </div>
  );
}
