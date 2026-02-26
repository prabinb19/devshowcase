"use client";

import { useSession } from "next-auth/react";
import { useEffect, useRef, useState, useCallback } from "react";
import type { SSEEvent } from "@/types";

interface AppUser {
  name?: string | null;
  email?: string | null;
  image?: string | null;
  githubId: string;
  githubUsername: string;
}

export function useUser(): AppUser | null {
  const { data: session } = useSession();
  if (!session?.user) return null;
  const u = session.user as Record<string, unknown>;
  return {
    name: u.name as string | null,
    email: u.email as string | null,
    image: u.image as string | null,
    githubId: (u.githubId as string) ?? "",
    githubUsername: (u.githubUsername as string) ?? "",
  };
}

export function useSSE(url: string | null) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [isDone, setIsDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  const reset = useCallback(() => {
    setEvents([]);
    setIsDone(false);
    setError(null);
  }, []);

  useEffect(() => {
    if (!url) return;

    const es = new EventSource(url);
    sourceRef.current = es;

    es.addEventListener("status", (e) => {
      try {
        const data = JSON.parse(e.data);
        setEvents((prev) => [...prev, data]);
      } catch {
        // non-JSON status — treat as string
        setEvents((prev) => [...prev, { stage: "info", message: e.data }]);
      }
    });

    es.addEventListener("done", () => {
      setIsDone(true);
      es.close();
    });

    es.addEventListener("error", () => {
      if (es.readyState === EventSource.CLOSED) return;
      setError("Connection lost");
      es.close();
    });

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) return;
      setError("Connection lost");
      es.close();
    };

    return () => {
      es.close();
    };
  }, [url]);

  return { events, isDone, error, reset };
}
