import { NextRequest, NextResponse } from "next/server";

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
    // Forward the code to the backend — we need the user's GitHub info from the cookie/session
    // The backend will exchange it for tokens
    const res = await fetch(`${API_BASE}/api/linkedin/callback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
