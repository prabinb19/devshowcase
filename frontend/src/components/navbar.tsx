"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { signOut } from "next-auth/react";
import { useUser } from "@/lib/hooks";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/drafts", label: "Drafts" },
  { href: "/history", label: "History" },
  { href: "/settings", label: "Settings" },
];

export function Navbar() {
  const user = useUser();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <nav className="bg-win98-silver bevel-outset">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
        <div className="flex items-center gap-6">
          <Link
            href="/dashboard"
            className="text-lg font-bold uppercase text-win98-navy"
          >
            DevShowcase
          </Link>
          <div className="hidden items-center gap-4 sm:flex">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm font-bold text-win98-black uppercase hover:text-win98-navy"
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {user && (
            <>
              {user.image && (
                <div className="bevel-inset p-0.5">
                  <Image
                    src={user.image}
                    alt={user.name ?? "Avatar"}
                    width={32}
                    height={32}
                  />
                </div>
              )}
              <span className="hidden text-sm font-bold text-win98-black sm:block">
                {user.name ?? user.githubUsername}
              </span>
              <button
                onClick={() => signOut({ callbackUrl: "/" })}
                className="hidden text-sm font-bold text-win98-black bg-win98-silver bevel-outset px-2 py-1 active:bevel-pressed sm:block"
              >
                Sign out
              </button>
            </>
          )}
          {/* Mobile menu button */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="inline-flex items-center justify-center p-1 text-win98-black bevel-outset sm:hidden"
            aria-label="Toggle menu"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              {mobileOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>
      </div>
      {/* Mobile dropdown */}
      {mobileOpen && (
        <div className="bevel-inset mx-1 mb-1 px-4 pb-3 pt-2 sm:hidden">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setMobileOpen(false)}
              className="block py-2 text-sm font-bold text-win98-black uppercase hover:text-win98-navy"
            >
              {link.label}
            </Link>
          ))}
          {user && (
            <button
              onClick={() => signOut({ callbackUrl: "/" })}
              className="block w-full py-2 text-left text-sm font-bold text-win98-black"
            >
              Sign out
            </button>
          )}
        </div>
      )}
    </nav>
  );
}
