import { BrainApiError } from "./brain-api";

export type DirectConversation = {
  id: string;
  organization_id: string;
  other_user_id: string;
  other_display_name: string;
  other_email: string;
  can_send: boolean;
  unread_count: number;
  latest_message_id: string | null;
  first_unread_message_id: string | null;
  created_at: string;
  updated_at: string;
};

export type DirectMessage = {
  id: string;
  organization_id: string;
  conversation_id: string;
  author_user_id: string;
  author_display_name: string;
  is_mine: boolean;
  body: string;
  body_sha256: string;
  sequence: number;
  revision: number;
  edited_at: string | null;
  deleted_at: string | null;
  can_edit: boolean;
  can_delete: boolean;
  created_at: string;
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

async function dmMutation<T>(
  accessToken: string,
  path: string,
  method: "PATCH" | "DELETE",
  body: object,
): Promise<T> {
  if (!accessToken.trim()) throw new Error("A server-side WorkOS access token is required");
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    method,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(body),
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
  return (await response.json()) as T;
}

async function dmFetch<T>(accessToken: string, path: string): Promise<T> {
  if (!accessToken.trim()) throw new Error("A server-side WorkOS access token is required");
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    cache: "no-store",
    headers: {
      Accept: "application/json",
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
  return (await response.json()) as T;
}

export function listDirectConversations(
  accessToken: string,
  organizationId: string,
): Promise<DirectConversation[]> {
  return dmFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/direct-messages`,
  );
}

export function getDirectMessage(
  accessToken: string,
  organizationId: string,
  conversationId: string,
  messageId: string,
): Promise<DirectMessage> {
  return dmFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/direct-messages/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}`,
  );
}

export function listDirectMessages(
  accessToken: string,
  organizationId: string,
  conversationId: string,
  limit = 200,
  beforeSequence?: number | null,
): Promise<DirectMessage[]> {
  const boundedLimit = Math.min(Math.max(Math.trunc(limit), 1), 200);
  const params = new URLSearchParams({ limit: String(boundedLimit) });
  if (beforeSequence !== undefined && beforeSequence !== null) {
    params.set("before_sequence", String(Math.max(1, Math.trunc(beforeSequence))));
  }
  return dmFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/direct-messages/${encodeURIComponent(conversationId)}/messages?${params.toString()}`,
  );
}

export function editDirectMessage(
  accessToken: string,
  organizationId: string,
  conversationId: string,
  messageId: string,
  body: string,
  expectedRevision: number,
): Promise<DirectMessage> {
  return dmMutation(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/direct-messages/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}`,
    "PATCH",
    { body, expected_revision: expectedRevision },
  );
}

export function retractDirectMessage(
  accessToken: string,
  organizationId: string,
  conversationId: string,
  messageId: string,
  expectedRevision: number,
): Promise<DirectMessage> {
  return dmMutation(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/direct-messages/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}`,
    "DELETE",
    { expected_revision: expectedRevision },
  );
}
