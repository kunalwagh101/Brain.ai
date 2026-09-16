import { BrainApiError } from "./brain-api";

export type AdminMember = {
  membership_id: string;
  user_id: string;
  email: string;
  display_name: string | null;
  role: string;
  joined_at: string;
};

export type AdminIntegration = {
  id: string;
  provider: string;
  display_name: string;
  status: string;
  health: string;
  scopes: string[];
  last_synced_at: string | null;
  last_error_code: string | null;
  created_at: string;
  revoked_at: string | null;
};

export type AdminAIModel = {
  id: string;
  model_key: string;
  display_name: string;
  enabled: boolean;
  max_output_tokens: number | null;
};

export type AdminAIProvider = {
  id: string;
  provider_key: string;
  display_name: string;
  adapter_kind: string;
  api_url: string;
  status: string;
  models: AdminAIModel[];
  credential_rotated_at: string | null;
  revoked_at: string | null;
};

export type AdminAPIGrant = {
  id: string;
  grant_key: string;
  display_name: string;
  owner_user_id: string;
  owner_email: string | null;
  environment: string;
  scopes: string[];
  status: string;
  expires_at: string | null;
  credential_present: boolean;
  credential_rotated_at: string | null;
  last_used_at: string | null;
  usage_count: number;
  last_usage_success: boolean | null;
  last_usage_latency_ms: number | null;
};

export type AdminAPIService = {
  id: string;
  service_key: string;
  display_name: string;
  provider_name: string;
  base_url: string | null;
  grants: AdminAPIGrant[];
};

export type AdminCenter = {
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  members: AdminMember[];
  integrations: AdminIntegration[];
  ai_providers: AdminAIProvider[];
  api_services: AdminAPIService[];
  summary: {
    member_count: number;
    integration_count: number;
    unhealthy_integration_count: number;
    ai_provider_count: number;
    enabled_ai_model_count: number;
    api_service_count: number;
    active_api_grant_count: number;
    expiring_api_grant_count: number;
  };
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

async function adminApiFetch<T>(
  accessToken: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  if (!accessToken.trim()) throw new Error("A server-side WorkOS access token is required");
  if (!path.startsWith("/api/v1/")) throw new Error("Brain API path must be under /api/v1/");
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
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

export function getAdminCenter(accessToken: string, organizationId: string): Promise<AdminCenter> {
  return adminApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/admin-center`,
  );
}

export function inviteOrganizationMember(
  accessToken: string,
  organizationId: string,
  email: string,
  role: string,
): Promise<unknown> {
  return adminApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/memberships`,
    { method: "POST", body: JSON.stringify({ user_email: email, role }) },
  );
}

export function changeOrganizationMemberRole(
  accessToken: string,
  organizationId: string,
  membershipId: string,
  role: string,
): Promise<unknown> {
  return adminApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/memberships/${encodeURIComponent(membershipId)}/role`,
    { method: "POST", body: JSON.stringify({ role }) },
  );
}

export function removeOrganizationMember(
  accessToken: string,
  organizationId: string,
  membershipId: string,
): Promise<void> {
  return adminApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/memberships/${encodeURIComponent(membershipId)}`,
    { method: "DELETE" },
  );
}

export function revokeIntegration(
  accessToken: string,
  organizationId: string,
  integrationId: string,
): Promise<unknown> {
  return adminApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/integrations/${encodeURIComponent(integrationId)}/revoke`,
    { method: "POST" },
  );
}

export function setAIProviderEnabled(
  accessToken: string,
  organizationId: string,
  providerId: string,
  enabled: boolean,
): Promise<unknown> {
  return adminApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/ai/providers/${encodeURIComponent(providerId)}/status`,
    { method: "POST", body: JSON.stringify({ enabled }) },
  );
}

export function revokeAIProvider(
  accessToken: string,
  organizationId: string,
  providerId: string,
): Promise<unknown> {
  return adminApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/ai/providers/${encodeURIComponent(providerId)}/revoke`,
    { method: "POST" },
  );
}

export function setAIModelEnabled(
  accessToken: string,
  organizationId: string,
  modelId: string,
  enabled: boolean,
): Promise<unknown> {
  return adminApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/ai/models/${encodeURIComponent(modelId)}/status`,
    { method: "POST", body: JSON.stringify({ enabled }) },
  );
}

export function setAPIGrantEnabled(
  accessToken: string,
  organizationId: string,
  grantId: string,
  enabled: boolean,
  reason: string | null,
): Promise<unknown> {
  return adminApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/api-registry/grants/${encodeURIComponent(grantId)}/status`,
    { method: "POST", body: JSON.stringify({ enabled, reason }) },
  );
}

export function revokeAPIGrant(
  accessToken: string,
  organizationId: string,
  grantId: string,
  reason: string | null,
): Promise<unknown> {
  return adminApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/api-registry/grants/${encodeURIComponent(grantId)}/revoke`,
    { method: "POST", body: JSON.stringify({ reason }) },
  );
}
