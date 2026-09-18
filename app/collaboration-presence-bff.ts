import { BrainApiError } from "./brain-api";
import {
  BrainMembershipError,
  requireBrainOrganizationMembership,
  requireUuid,
} from "./brain-membership";

const PRESENCE_ROLES = new Set(["owner", "admin", "executive", "manager", "member"]);
const CONTEXT_KINDS = new Set(["channel", "dm"]);

export class CollaborationPresenceBffError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "CollaborationPresenceBffError";
    this.status = status;
  }
}

function apiBaseUrl(): string {
  const configured = process.env.BRAIN_API_BASE_URL?.trim();
  if (!configured) throw new CollaborationPresenceBffError(503, "Brain API is unavailable");
  const parsed = new URL(configured);
  if (process.env.NODE_ENV === "production" && parsed.protocol !== "https:") {
    throw new CollaborationPresenceBffError(503, "Brain API transport is invalid");
  }
  return configured.replace(/\/$/, "");
}

async function requirePresenceMembership(
  accessToken: string,
  organizationId: string,
): Promise<void> {
  try {
    const organization = await requireBrainOrganizationMembership(accessToken, organizationId);
    if (!PRESENCE_ROLES.has(organization.role)) {
      throw new CollaborationPresenceBffError(
        403,
        "Collaboration presence is unavailable for this role",
      );
    }
  } catch (error) {
    if (error instanceof CollaborationPresenceBffError) throw error;
    if (error instanceof BrainMembershipError) {
      throw new CollaborationPresenceBffError(error.status, error.message);
    }
    throw error;
  }
}

function normalizeContextKind(value: string): "channel" | "dm" {
  if (!CONTEXT_KINDS.has(value)) {
    throw new CollaborationPresenceBffError(400, "Invalid collaboration context");
  }
  return value as "channel" | "dm";
}

function normalizeContextId(value: string): string {
  try {
    return requireUuid(value, "contextId");
  } catch (error) {
    if (error instanceof BrainMembershipError) {
      throw new CollaborationPresenceBffError(error.status, error.message);
    }
    throw error;
  }
}

async function forward<T>(
  accessToken: string,
  path: string,
  method: "GET" | "POST" | "PUT" | "DELETE",
): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    method,
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
  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}

export async function handlePresenceHeartbeat(
  accessToken: string,
  organizationId: string,
): Promise<unknown> {
  await requirePresenceMembership(accessToken, organizationId);
  return forward(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/collaboration-presence/heartbeat`,
    "POST",
  );
}

export async function handlePresenceContext(
  accessToken: string,
  organizationId: string,
  contextKind: string,
  contextId: string,
): Promise<unknown> {
  await requirePresenceMembership(accessToken, organizationId);
  const kind = normalizeContextKind(contextKind);
  const id = normalizeContextId(contextId);
  return forward(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/collaboration-presence/${kind}/${encodeURIComponent(id)}`,
    "GET",
  );
}

export async function handleTypingState(
  accessToken: string,
  organizationId: string,
  contextKind: string,
  contextId: string,
  active: boolean,
): Promise<void> {
  await requirePresenceMembership(accessToken, organizationId);
  const kind = normalizeContextKind(contextKind);
  const id = normalizeContextId(contextId);
  return forward(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/collaboration-presence/${kind}/${encodeURIComponent(id)}/typing`,
    active ? "PUT" : "DELETE",
  );
}
