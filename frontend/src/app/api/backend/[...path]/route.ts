/**
 * Next.js API proxy — forwards authenticated requests to the Python backend.
 *
 * The frontend calls `/api/backend/<path>` instead of hitting the backend
 * directly. This route handler reads the NextAuth session cookie, re-encodes
 * a JWT with the same NEXTAUTH_SECRET, and forwards it as a Bearer token so
 * the backend can verify the caller's identity without trusting raw headers.
 */

import { NextRequest, NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";
import * as jose from "jose";

// Server-only env var for Docker; falls back to the public URL for local dev
const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function proxyRequest(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const { path } = await params;
  const backendPath = `/api/${path.join("/")}`;
  const url = new URL(backendPath, BACKEND_URL);

  // Preserve query string
  const qs = request.nextUrl.search;
  if (qs) {
    url.search = qs;
  }

  // Read the NextAuth session token from the cookie
  const sessionToken = await getToken({ req: request });
  const headers = new Headers();

  // Forward content-type
  const ct = request.headers.get("content-type");
  if (ct) headers.set("Content-Type", ct);

  if (sessionToken) {
    const secret = process.env.NEXTAUTH_SECRET;
    if (!secret) {
      return NextResponse.json(
        { detail: "Auth not configured" },
        { status: 500 }
      );
    }

    // Re-encode a minimal JWT for the backend
    const encodedSecret = new TextEncoder().encode(secret);
    const backendToken = await new jose.SignJWT({
      githubId: String(sessionToken.githubId ?? ""),
      githubUsername: String(sessionToken.githubUsername ?? ""),
    })
      .setProtectedHeader({ alg: "HS256" })
      .setIssuedAt()
      .setExpirationTime("5m")
      .sign(encodedSecret);

    headers.set("Authorization", `Bearer ${backendToken}`);
  }

  // Forward the request body for non-GET methods
  let body: BodyInit | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    body = await request.arrayBuffer();
  }

  try {
    const backendRes = await fetch(url.toString(), {
      method: request.method,
      headers,
      body,
    });

    // Stream the response back
    const resHeaders = new Headers();
    backendRes.headers.forEach((value, key) => {
      // Skip hop-by-hop headers
      if (!["transfer-encoding", "connection"].includes(key.toLowerCase())) {
        resHeaders.set(key, value);
      }
    });

    return new NextResponse(backendRes.body, {
      status: backendRes.status,
      headers: resHeaders,
    });
  } catch {
    return NextResponse.json(
      { detail: "Backend unavailable" },
      { status: 502 }
    );
  }
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
