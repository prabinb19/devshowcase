"use client";

import { signIn } from "next-auth/react";
import { Button } from "@/components/ui/button";

export function LandingContent() {
  return (
    <div className="min-h-screen bg-white dark:bg-gray-950">
      {/* Hero */}
      <section className="flex flex-col items-center justify-center px-4 pb-16 pt-24 sm:pt-32">
        <div className="mx-auto max-w-3xl text-center">
          <h1 className="text-4xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-6xl">
            Turn GitHub repos into
            <span className="bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
              {" "}LinkedIn posts
            </span>
          </h1>
          <p className="mt-6 text-lg leading-8 text-gray-600 dark:text-gray-400 sm:text-xl">
            Paste a repo URL. Our AI analyzes the code, captures screenshots,
            and generates a polished LinkedIn post — ready to publish in minutes.
          </p>
          <div className="mt-10">
            <Button
              onClick={() => signIn("github", { callbackUrl: "/dashboard" })}
              className="px-8 py-3 text-base"
            >
              Sign in with GitHub
            </Button>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="border-t border-gray-100 bg-gray-50 px-4 py-20 dark:border-gray-800 dark:bg-gray-900">
        <div className="mx-auto max-w-4xl">
          <h2 className="mb-12 text-center text-2xl font-bold text-gray-900 dark:text-white sm:text-3xl">
            How It Works
          </h2>
          <div className="grid gap-10 sm:grid-cols-3">
            <div className="flex flex-col items-center gap-4 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-100 text-2xl font-bold text-blue-600 dark:bg-blue-900/50 dark:text-blue-400">
                1
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Paste a URL
              </h3>
              <p className="text-sm leading-6 text-gray-600 dark:text-gray-400">
                Drop in any public GitHub repository URL. We fetch the README,
                file structure, and key config files.
              </p>
            </div>
            <div className="flex flex-col items-center gap-4 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-100 text-2xl font-bold text-blue-600 dark:bg-blue-900/50 dark:text-blue-400">
                2
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                AI Analyzes
              </h3>
              <p className="text-sm leading-6 text-gray-600 dark:text-gray-400">
                Claude identifies what makes the project interesting — tech stack,
                highlights, and the best screenshots to feature.
              </p>
            </div>
            <div className="flex flex-col items-center gap-4 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-100 text-2xl font-bold text-blue-600 dark:bg-blue-900/50 dark:text-blue-400">
                3
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Review & Publish
              </h3>
              <p className="text-sm leading-6 text-gray-600 dark:text-gray-400">
                Edit the generated post, tweak screenshots, and publish directly
                to LinkedIn — or save as a draft for later.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Pipeline Details */}
      <section className="px-4 py-20">
        <div className="mx-auto max-w-4xl">
          <h2 className="mb-12 text-center text-2xl font-bold text-gray-900 dark:text-white sm:text-3xl">
            Under the Hood
          </h2>
          <div className="grid gap-6 sm:grid-cols-2">
            <div className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-900">
              <h3 className="mb-2 font-semibold text-gray-900 dark:text-white">
                Ingest
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Fetches repo metadata, README, file tree, and config files via
                the GitHub API. SSRF-protected — only public GitHub repos allowed.
              </p>
            </div>
            <div className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-900">
              <h3 className="mb-2 font-semibold text-gray-900 dark:text-white">
                Analyze
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Claude identifies the project type, tech stack, key highlights,
                and determines the best screenshot strategy.
              </p>
            </div>
            <div className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-900">
              <h3 className="mb-2 font-semibold text-gray-900 dark:text-white">
                Capture
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Extracts README images or generates a branded project card.
                Images are processed, optimized, and stored on Cloudflare R2.
              </p>
            </div>
            <div className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-900">
              <h3 className="mb-2 font-semibold text-gray-900 dark:text-white">
                Generate
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Crafts a LinkedIn-optimized post with hook, body, alt texts,
                and a first comment — all following platform best practices.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Security */}
      <section className="border-t border-gray-100 bg-gray-50 px-4 py-20 dark:border-gray-800 dark:bg-gray-900">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="mb-8 text-2xl font-bold text-gray-900 dark:text-white sm:text-3xl">
            Built with Security in Mind
          </h2>
          <div className="grid gap-6 text-left sm:grid-cols-3">
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                Secret Redaction
              </h3>
              <p className="text-xs leading-5 text-gray-600 dark:text-gray-400">
                API keys, tokens, and credentials are stripped from repo content
                before any LLM processing.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                Encrypted Tokens
              </h3>
              <p className="text-xs leading-5 text-gray-600 dark:text-gray-400">
                LinkedIn OAuth tokens are encrypted at rest with Fernet
                symmetric encryption. Never stored in plaintext.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                SSRF Protection
              </h3>
              <p className="text-xs leading-5 text-gray-600 dark:text-gray-400">
                URL validation restricts to public GitHub repos only. Private
                IPs, localhost, and non-GitHub hosts are rejected.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-200 px-4 py-8 dark:border-gray-800">
        <p className="text-center text-xs text-gray-500 dark:text-gray-500">
          DevShowcase — Open source on GitHub
        </p>
      </footer>
    </div>
  );
}
