import { authkitProxy } from "@workos-inc/authkit-nextjs";
import { NextFetchEvent, NextRequest, NextResponse } from "next/server";

const workos = authkitProxy();

function ready(): boolean {
  const required = [
    process.env.WORKOS_CLIENT_ID,
    process.env.WORKOS_API_KEY,
    process.env.WORKOS_COOKIE_PASSWORD,
    process.env.NEXT_PUBLIC_WORKOS_REDIRECT_URI,
    process.env.BRAIN_API_BASE_URL,
  ];
  if (required.some((value) => !value?.trim())) return false;
  if (process.env.WORKOS_COOKIE_PASSWORD!.length < 32) return false;
  try {
    const redirect = new URL(process.env.NEXT_PUBLIC_WORKOS_REDIRECT_URI!);
    const api = new URL(process.env.BRAIN_API_BASE_URL!);
    return redirect.pathname === "/auth/callback"
      && !redirect.search && !redirect.hash && !redirect.username && !redirect.password
      && !api.username && !api.password && !api.hash
      && (process.env.NODE_ENV !== "production"
        || (redirect.protocol === "https:" && api.protocol === "https:"));
  } catch {
    return false;
  }
}

export default function proxy(request: NextRequest, event: NextFetchEvent) {
  if (ready()) return workos(request, event);
  if (request.nextUrl.pathname.startsWith("/api/brain/")) {
    return NextResponse.json({ detail: "Brain authentication is not configured" }, { status: 503 });
  }
  return NextResponse.redirect(new URL("/setup", request.url));
}

// Keep the matcher narrow. AuthKit must run where withAuth() is used, but static
// assets must not be intercepted by a broad catch-all proxy.
export const config = {
  matcher: ["/", "/api/brain/:path*", "/sign-in", "/auth/callback"],
};
