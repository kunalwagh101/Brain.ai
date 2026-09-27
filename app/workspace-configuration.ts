// Shared by the Next.js proxy and the setup page. Never return secret values.
const required = [
  "WORKOS_CLIENT_ID",
  "WORKOS_API_KEY",
  "WORKOS_COOKIE_PASSWORD",
  "NEXT_PUBLIC_WORKOS_REDIRECT_URI",
  "BRAIN_API_BASE_URL",
] as const;

export function demoModeReady(
  env: Record<string, string | undefined>,
  production: boolean,
): boolean {
  if (env.BRAIN_ENVIRONMENT !== "staging" || env.BRAIN_DEMO_SIGNUP_ENABLED !== "true") return false;
  try {
    const url = new URL(env.BRAIN_API_BASE_URL ?? "");
    return !url.username && !url.password && !url.search && !url.hash
      && url.pathname === "/" && (production ? url.protocol === "https:" : ["http:", "https:"].includes(url.protocol));
  } catch {
    return false;
  }
}

export function configurationIssues(
  env: Record<string, string | undefined>,
  production: boolean,
): string[] {
  const issues = new Set<string>();
  for (const name of required) if (!env[name]?.trim()) issues.add(name);

  if (env.WORKOS_CLIENT_ID?.trim() && !env.WORKOS_CLIENT_ID.startsWith("client_")) {
    issues.add("WORKOS_CLIENT_ID");
  }
  if (env.WORKOS_API_KEY?.trim() && !env.WORKOS_API_KEY.startsWith("sk_")) {
    issues.add("WORKOS_API_KEY");
  }
  if (env.WORKOS_COOKIE_PASSWORD?.trim() && env.WORKOS_COOKIE_PASSWORD.length < 32) {
    issues.add("WORKOS_COOKIE_PASSWORD");
  }

  if (env.NEXT_PUBLIC_WORKOS_REDIRECT_URI?.trim()) {
    try {
      const uri = new URL(env.NEXT_PUBLIC_WORKOS_REDIRECT_URI);
      if (uri.pathname !== "/auth/callback" || uri.search || uri.hash || uri.username || uri.password
        || !["http:", "https:"].includes(uri.protocol) || (production && uri.protocol !== "https:")) {
        issues.add("NEXT_PUBLIC_WORKOS_REDIRECT_URI");
      }
    } catch {
      issues.add("NEXT_PUBLIC_WORKOS_REDIRECT_URI");
    }
  }
  if (env.BRAIN_API_BASE_URL?.trim()) {
    try {
      const uri = new URL(env.BRAIN_API_BASE_URL);
      if (uri.pathname !== "/" || uri.search || uri.hash || uri.username || uri.password
        || !["http:", "https:"].includes(uri.protocol) || (production && uri.protocol !== "https:")) {
        issues.add("BRAIN_API_BASE_URL");
      }
    } catch {
      issues.add("BRAIN_API_BASE_URL");
    }
  }

  return required.filter((name) => issues.has(name));
}
