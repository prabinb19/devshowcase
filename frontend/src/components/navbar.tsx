"use client";

import Link from "next/link";
import Image from "next/image";
import { signOut } from "next-auth/react";
import { useUser } from "@/lib/hooks";

export function Navbar() {
  const user = useUser();

  return (
    <nav className="border-b border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
        <div className="flex items-center gap-6">
          <Link
            href="/dashboard"
            className="text-lg font-semibold text-gray-900 dark:text-white"
          >
            DevShowcase
          </Link>
          <div className="hidden items-center gap-4 sm:flex">
            <Link
              href="/dashboard"
              className="text-sm text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
            >
              Dashboard
            </Link>
            <Link
              href="/drafts"
              className="text-sm text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
            >
              Drafts
            </Link>
          </div>
        </div>
        {user && (
          <div className="flex items-center gap-3">
            {user.image && (
              <Image
                src={user.image}
                alt={user.name ?? "Avatar"}
                width={32}
                height={32}
                className="rounded-full"
              />
            )}
            <span className="hidden text-sm text-gray-700 dark:text-gray-300 sm:block">
              {user.name ?? user.githubUsername}
            </span>
            <button
              onClick={() => signOut({ callbackUrl: "/" })}
              className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}
