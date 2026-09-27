import { authkitProxy } from "@workos-inc/authkit-nextjs";
import { NextFetchEvent, NextRequest, NextResponse } from "next/server";
import { configurationIssues, demoModeReady } from "./app/workspace-configuration";

const workos = authkitProxy();

export default function proxy(request: NextRequest, event: NextFetchEvent) {
  const demoReady = demoModeReady(process.env, process.env.NODE_ENV === "production");
  const workosReady = !configurationIssues(process.env, process.env.NODE_ENV === "production").length;
  // A cookie is only a hint here. FastAPI validates and revokes the bearer on
  // every request. Never derive membership or a user identity in the proxy.
  const demoSurface = request.nextUrl.pathname === "/" || request.nextUrl.pathname.startsWith("/api/brain/");
  if (demoReady && demoSurface && request.cookies.has("brain_demo_session")) return NextResponse.next();
  if (workosReady) {
    return workos(request, event);
  }
  if (request.nextUrl.pathname.startsWith("/api/brain/")) {
    return NextResponse.json({ detail: "Authentication required" }, { status: demoReady ? 401 : 503 });
  }
  return NextResponse.redirect(new URL(demoReady ? "/demo-signup" : "/setup", request.url));
}

// Keep the matcher narrow. AuthKit must run where withAuth() is used, but static
// assets must not be intercepted by a broad catch-all proxy.
export const config = {
  matcher: ["/", "/api/brain/:path*", "/sign-in", "/auth/callback"],
};
