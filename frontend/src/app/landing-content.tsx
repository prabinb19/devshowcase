"use client";

import { signIn } from "next-auth/react";
import { Button } from "@/components/ui/button";

export function LandingContent() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="mx-auto max-w-2xl text-center">
        <h1 className="text-5xl font-bold tracking-tight text-gray-900 dark:text-white">
          DevShowcase
        </h1>
        <p className="mt-4 text-xl text-gray-600 dark:text-gray-400">
          Turn GitHub repos into LinkedIn posts with AI
        </p>

        <div className="mt-12 grid gap-8 sm:grid-cols-3">
          <div className="flex flex-col items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-lg font-semibold text-blue-600 dark:bg-blue-900 dark:text-blue-300">
              1
            </div>
            <h3 className="font-medium text-gray-900 dark:text-white">Paste URL</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Drop in any public GitHub repository URL
            </p>
          </div>
          <div className="flex flex-col items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-lg font-semibold text-blue-600 dark:bg-blue-900 dark:text-blue-300">
              2
            </div>
            <h3 className="font-medium text-gray-900 dark:text-white">AI Analyzes</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              We ingest, analyze, and capture screenshots
            </p>
          </div>
          <div className="flex flex-col items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-lg font-semibold text-blue-600 dark:bg-blue-900 dark:text-blue-300">
              3
            </div>
            <h3 className="font-medium text-gray-900 dark:text-white">Get Draft</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Review, edit, and publish your LinkedIn post
            </p>
          </div>
        </div>

        <div className="mt-12">
          <Button
            onClick={() => signIn("github", { callbackUrl: "/dashboard" })}
            className="px-8 py-3 text-base"
          >
            Sign in with GitHub
          </Button>
        </div>
      </div>
    </div>
  );
}
