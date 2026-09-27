import { withAuth } from "@workos-inc/authkit-nextjs";
import { cookies } from "next/headers";
import { configurationIssues, demoModeReady } from "./workspace-configuration";

export const DEMO_COOKIE = "brain_demo_session";
const API_TIMEOUT_MS = 10000;

export function demoAvailable(): boolean {
  return demoModeReady(process.env, process.env.NODE_ENV === "production");
}

type BrainSession = {
  user: { firstName?: string | null; lastName?: string | null; email?: string | null } | null;
  accessToken: string | null;
  isDemo: boolean;
};

export async function demoApi(path: string, init: RequestInit): Promise<Response> {
  if (!demoAvailable() || !path.startsWith("/api/v1/")) {
    throw new Error("Staging demo API is unavailable");
  }
  const base = process.env.BRAIN_API_BASE_URL!.replace(/\/$/, "");
  return fetch(`${base}${path}`, {
    ...init, cache: "no-store", signal: AbortSignal.timeout(API_TIMEOUT_MS),
  });
}

export async function getBrainSession(): Promise<BrainSession> {
  if (demoAvailable()) {
    const token = (await cookies()).get(DEMO_COOKIE)?.value;
    if (token?.startsWith("brdemo_") && token.length <= 128) {
      const response = await demoApi("/api/v1/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const user = await response.json() as { email: string; display_name: string | null };
        return {
          user: { firstName: user.display_name || "Demo user", email: user.email },
          accessToken: token,
          isDemo: true,
        };
      }
      if (response.status !== 401 && response.status !== 403) {
        throw new Error(`Demo session lookup failed: ${response.status}`);
      }
    }
  }
  if (!configurationIssues(process.env, process.env.NODE_ENV === "production").length) {
    const session = await withAuth();
    return { user: session.user ?? null, accessToken: session.accessToken ?? null, isDemo: false };
  }
  return { user: null, accessToken: null, isDemo: false };
}

export async function revokeDemoSession(token: string): Promise<void> {
  const response = await demoApi("/api/v1/demo-sessions/current", {
    method: "DELETE", headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok && response.status !== 401) throw new Error("Demo sign-out failed");
  (await cookies()).delete(DEMO_COOKIE);
}
