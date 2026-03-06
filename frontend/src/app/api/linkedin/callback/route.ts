import { NextRequest, NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";
import * as jose from "jose";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get("code");
  const state = searchParams.get("state");
  const error = searchParams.get("error");

  if (error) {
    return NextResponse.redirect(
      new URL(`/drafts?linkedin_error=${error}`, request.url)
    );
  }

  if (!code || !state) {
    return NextResponse.redirect(
      new URL("/drafts?linkedin_error=missing_params", request.url)
    );
  }

  try {
    // Read the NextAuth session and build a JWT for the backend
    const sessionToken = await getToken({ req: request });
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    if (sessionToken) {
      const secret = process.env.NEXTAUTH_SECRET;
      if (secret) {
        const encodedSecret = new TextEncoder().encode(secret);
        const backendToken = await new jose.SignJWT({
          githubId: String(sessionToken.githubId ?? ""),
          githubUsername: String(sessionToken.githubUsername ?? ""),
        })
          .setProtectedHeader({ alg: "HS256" })
          .setIssuedAt()
          .setExpirationTime("5m")
          .sign(encodedSecret);

        headers["Authorization"] = `Bearer ${backendToken}`;
      }
    }

    const res = await fetch(`${API_BASE}/api/linkedin/callback`, {
      method: "POST",
      headers,
      body: JSON.stringify({ code, state }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      return NextResponse.redirect(
        new URL(
          `/drafts?linkedin_error=${encodeURIComponent(body.detail ?? "callback_failed")}`,
          request.url
        )
      );
    }

    return NextResponse.redirect(
      new URL("/drafts?linkedin_connected=true", request.url)
    );
  } catch {
    return NextResponse.redirect(
      new URL("/drafts?linkedin_error=network_error", request.url)
    );
  }
}
