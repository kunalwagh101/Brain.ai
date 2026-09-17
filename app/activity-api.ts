import { BrainApiError } from "./brain-api";

export type ActivityKind =
  | "mention"
  | "thread_reply"
  | "reaction"
  | "direct_message"
  | "channel_activity"
  | "agent_approval"
  | "agent_completed"
  | "agent_failed"
  | "project_update"
  | "blocker_update"
  | "integration_failure";

export type ActivityItem = {
  id: string;
  kind: ActivityKind;
  actor_display_name: string | null;
  label: string;
  context_label: string | null;
  href: string;
  read: boolean;
  created_at: string;
};

export type ActivitySummary = {
  unread_count: number;
  items: ActivityItem[];
};

export type ActivityPreferences = {
  mentions: boolean;
  thread_replies: boolean;
  direct_messages: boolean;
  channel_activity: boolean;
  agent_approvals: boolean;
  agent_run_events: boolean;
  project_updates: boolean;
  integration_failures: boolean;
};

function apiBaseUrl(): string {
  const configured = process.env.BRAIN_API_BASE_URL?.trim();
  if (!configured) throw new Error("BRAIN_API_BASE_URL is required for the production frontend");
  const parsed = new URL(configured);
  if (process.env.NODE_ENV === "production" && parsed.protocol !== "https:") {
    throw new Error("BRAIN_API_BASE_URL must use HTTPS in production");
  }
  return configured.replace(/\/$/, "");
}

async function activityFetch<T>(accessToken: string, path: string, init?: RequestInit): Promise<T> {
  if (!accessToken.trim()) throw new Error("A server-side WorkOS access token is required");
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...init?.headers,
      Authorization: `Bearer ${accessToken}`,
    },
  });
  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      detail = { error: "non_json_error_response" };
    }
    throw new BrainApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function getActivity(
  accessToken: string,
  organizationId: string,
  limit = 50,
): Promise<ActivitySummary> {
  return activityFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/activity?limit=${limit}`,
  );
}

export function getActivityPreferences(
  accessToken: string,
  organizationId: string,
): Promise<ActivityPreferences> {
  return activityFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/activity/preferences`,
  );
}

export function updateActivityPreferences(
  accessToken: string,
  organizationId: string,
  values: Partial<ActivityPreferences>,
): Promise<ActivityPreferences> {
  return activityFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/activity/preferences`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    },
  );
}

export function markActivityRead(
  accessToken: string,
  organizationId: string,
  notificationId: string,
): Promise<void> {
  return activityFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/activity/${encodeURIComponent(notificationId)}/read`,
    { method: "POST" },
  );
}

export function markAllActivityRead(
  accessToken: string,
  organizationId: string,
): Promise<{ updated: number }> {
  return activityFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/activity/read-all`,
    { method: "POST" },
  );
}
