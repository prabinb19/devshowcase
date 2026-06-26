"use client";

import { useState, useEffect } from "react";
import { signIn } from "next-auth/react";
import Marquee from "react-fast-marquee";
import { Button } from "@/components/ui/button";

export function LandingContent() {
  const [visitorNum, setVisitorNum] = useState("0000");

  useEffect(() => {
    setVisitorNum(String(Math.floor(Math.random() * 9000 + 1000)));
  }, []);

  return (
    <div className="min-h-screen bg-win98-silver">
      {/* Hero */}
      <section className="flex flex-col items-center justify-center px-4 pb-16 pt-24 sm:pt-32">
        <div className="mx-auto max-w-3xl text-center">
          <h1 className="font-heading text-4xl font-bold uppercase tracking-tight text-win98-black sm:text-6xl rainbow-text">
            Turn GitHub repos into LinkedIn posts
          </h1>
          <p className="mt-6 text-lg leading-8 text-win98-black sm:text-xl">
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

      {/* Marquee */}
      <div className="bg-win98-navy py-2">
        <Marquee speed={60} gradient={false}>
          <span className="mx-8 text-win98-yellow font-bold uppercase tracking-wide">
            *** WELCOME TO DEVSHOWCASE *** YOUR #1 SOURCE FOR AI-POWERED LINKEDIN POSTS ***
            TURN ANY GITHUB REPO INTO A VIRAL POST *** FREE AND OPEN SOURCE ***
          </span>
        </Marquee>
      </div>

      {/* How It Works */}
      <section className="bg-win98-silver px-4 py-20">
        <div className="mx-auto max-w-4xl">
          <h2 className="mb-12 text-center text-2xl font-bold uppercase text-win98-black sm:text-3xl">
            How It Works
          </h2>
          <div className="grid gap-10 sm:grid-cols-3">
            {[
              {
                num: "1",
                title: "Paste a URL",
                desc: "Drop in any public GitHub repository URL. We fetch the README, file structure, and key config files.",
              },
              {
                num: "2",
                title: "AI Analyzes",
                desc: "The AI agent identifies what makes the project interesting — tech stack, highlights, and the best screenshots to feature.",
              },
              {
                num: "3",
                title: "Review & Publish",
                desc: "Edit the generated post, tweak screenshots, and publish directly to LinkedIn — or save as a draft for later.",
              },
            ].map((step) => (
              <div key={step.num} className="bg-win98-silver bevel-outset">
                <div className="win98-titlebar">
                  Step {step.num} - {step.title}
                </div>
                <div className="bevel-inset bg-white m-1 p-3">
                  <p className="text-sm text-win98-black">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pipeline Details */}
      <section className="px-4 py-20">
        <div className="mx-auto max-w-4xl">
          <h2 className="mb-12 text-center text-2xl font-bold uppercase text-win98-black sm:text-3xl">
            Under the Hood
          </h2>
          <div className="grid gap-6 sm:grid-cols-2">
            {[
              {
                title: "Ingest",
                desc: "Fetches repo metadata, README, file tree, and config files via the GitHub API. SSRF-protected — only public GitHub repos allowed.",
              },
              {
                title: "Analyze",
                desc: "The agent identifies the project type, tech stack, key highlights, and determines the best screenshot strategy.",
              },
              {
                title: "Capture",
                desc: "Extracts README images or generates a branded project card. Images are processed, optimized, and stored on Cloudflare R2.",
              },
              {
                title: "Generate",
                desc: "Crafts a LinkedIn-optimized post with hook, body, alt texts, and a first comment — all following platform best practices.",
              },
            ].map((item) => (
              <div key={item.title} className="bg-win98-silver bevel-outset">
                <div className="win98-titlebar">{item.title}</div>
                <div className="bevel-inset bg-white m-1 p-3">
                  <p className="text-sm text-win98-black">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Security */}
      <section className="bg-win98-silver px-4 py-20">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="mb-8 text-2xl font-bold uppercase text-win98-black sm:text-3xl">
            Built with Security in Mind
          </h2>
          <div className="grid gap-6 text-left sm:grid-cols-3">
            {[
              {
                title: "Secret Redaction",
                desc: "API keys, tokens, and credentials are stripped from repo content before any LLM processing.",
              },
              {
                title: "Encrypted Tokens",
                desc: "LinkedIn OAuth tokens are encrypted at rest with Fernet symmetric encryption. Never stored in plaintext.",
              },
              {
                title: "SSRF Protection",
                desc: "URL validation restricts to public GitHub repos only. Private IPs, localhost, and non-GitHub hosts are rejected.",
              },
            ].map((item) => (
              <div key={item.title} className="flex flex-col gap-2">
                <h3 className="text-sm font-bold uppercase text-win98-black">
                  {item.title}
                </h3>
                <p className="text-xs leading-5 text-win98-black">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Construction Stripes */}
      <div className="construction-stripes" />

      {/* Footer */}
      <footer className="bg-win98-silver px-4 py-8">
        <p className="text-center text-xs text-win98-black font-bold">
          DevShowcase — Open source on GitHub
        </p>
        <div className="mt-4 flex justify-center">
          <div className="bevel-inset bg-black px-4 py-2">
            <span className="font-mono text-sm text-win98-green">
              You are visitor #000{visitorNum}
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
