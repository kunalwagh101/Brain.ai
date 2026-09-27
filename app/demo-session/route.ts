import { NextRequest, NextResponse } from "next/server";
import { demoApi, demoAvailable, DEMO_COOKIE } from "../brain-session";
import { browserOrigin } from "../same-origin";

function back(request: NextRequest, error: string): NextResponse {
  return NextResponse.redirect(new URL(`/demo-signup?error=${error}`, browserOrigin(request)), 303);
}

export async function POST(request: NextRequest) {
  if (!demoAvailable()) return NextResponse.json({ detail: "Unavailable" }, { status: 404 });
  const origin = request.headers.get("origin");
  if (origin !== browserOrigin(request) || request.headers.get("sec-fetch-site") === "cross-site") {
    return back(request, "origin");
  }
  const size = Number(request.headers.get("content-length") ?? "0");
  if (size > 1024) return back(request, "name");
  const form = await request.formData();
  const raw = form.get("name");
  const name = typeof raw === "string" ? raw.trim().replace(/\s+/g, " ") : "";
  if (!name || name.length > 80) return back(request, "name");
  try {
    const response = await demoApi("/api/v1/demo-sessions", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (response.status === 429) return back(request, "limit");
    if (!response.ok) return back(request, "unavailable");
    const data = await response.json() as { access_token?: string; expires_at?: string };
    if (!data.access_token?.startsWith("brdemo_") || !data.expires_at) return back(request, "unavailable");
    const seconds = Math.floor((Date.parse(data.expires_at) - Date.now()) / 1000);
    if (!Number.isFinite(seconds) || seconds < 1 || seconds > 12 * 60 * 60) return back(request, "unavailable");
    const next = NextResponse.redirect(new URL("/", browserOrigin(request)), 303);
    next.cookies.set(DEMO_COOKIE, data.access_token, {
      httpOnly: true, secure: process.env.NODE_ENV === "production",
      sameSite: "lax", path: "/", maxAge: seconds,
    });
    next.headers.set("Cache-Control", "no-store");
    return next;
  } catch {
    return back(request, "unavailable");
  }
}
