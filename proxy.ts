import { authkitProxy } from "@workos-inc/authkit-nextjs";
import { NextFetchEvent, NextRequest, NextResponse } from "next/server";
import { configurationIssues } from "./app/workspace-configuration";

const workos = authkitProxy();

export default function proxy(request: NextRequest, event: NextFetchEvent) {
  if (!configurationIssues(process.env, process.env.NODE_ENV === "production").length) {
    return workos(request, event);
  }
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
