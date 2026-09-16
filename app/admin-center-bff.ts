import {
  changeAPIGrantEnvironment,
  changeAPIGrantOwner,
  changeAPIGrantScopes,
  changeOrganizationMemberRole,
  createAPIGrant,
  inviteOrganizationMember,
  removeOrganizationMember,
  revokeAIProvider,
  revokeAPIGrant,
  revokeIntegration,
  rotateAIProviderCredentials,
  rotateAPIGrantCredentials,
  setAIModelEnabled,
  setAIProviderEnabled,
  setAPIGrantEnabled,
} from "./admin-center-api";
import {
  BrainMembershipError,
  requireBrainOrganizationMembership,
  requireUuid,
} from "./brain-membership";

const ADMIN_ROLES = new Set(["owner", "admin"]);
const MEMBERSHIP_ROLES = new Set(["owner", "admin", "executive", "manager", "member", "guest"]);
const KEY_RE = /^[a-z0-9][a-z0-9._-]{0,95}$/;
const ENVIRONMENT_RE = /^[a-z0-9][a-z0-9._-]{0,63}$/;
const SCOPE_RE = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/;

export type AdminCenterAction =
  | { action: "member_invite"; email: string; role: string }
  | { action: "member_role"; membership_id: string; role: string }
  | { action: "member_remove"; membership_id: string }
  | { action: "integration_revoke"; integration_id: string }
  | { action: "ai_provider_status"; provider_id: string; enabled: boolean }
  | { action: "ai_provider_rotate"; provider_id: string; credentials: Record<string, string> }
  | { action: "ai_provider_revoke"; provider_id: string }
  | { action: "ai_model_status"; model_id: string; enabled: boolean }
  | {
      action: "api_grant_create";
      service_id: string;
      grant_key: string;
      display_name: string;
      owner_user_id: string;
      environment: string;
      scopes: string[];
      expires_at: string | null;
      credentials: Record<string, string>;
    }
  | { action: "api_grant_owner"; grant_id: string; owner_user_id: string; reason: string | null }
  | { action: "api_grant_scopes"; grant_id: string; scopes: string[]; reason: string | null }
  | { action: "api_grant_environment"; grant_id: string; environment: string; reason: string | null }
  | { action: "api_grant_rotate"; grant_id: string; credentials: Record<string, string>; reason: string | null }
  | { action: "api_grant_status"; grant_id: string; enabled: boolean; reason: string | null }
  | { action: "api_grant_revoke"; grant_id: string; reason: string | null };

export class AdminCenterBffError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "AdminCenterBffError";
    this.status = status;
  }
}

function invalid(status: number, message: string): never {
  throw new AdminCenterBffError(status, message);
}

function exactObject(value: unknown, allowed: Set<string>, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) invalid(400, `${label} must be an object`);
  const body = value as Record<string, unknown>;
  for (const key of Object.keys(body)) {
    if (!allowed.has(key)) invalid(400, `Unexpected ${label} field: ${key}`);
  }
  return body;
}

function requiredString(value: unknown, field: string, maxLength: number): string {
  if (typeof value !== "string") invalid(400, `${field} must be a string`);
  const normalized = value.trim();
  if (!normalized || normalized.length > maxLength) invalid(400, `${field} is invalid`);
  return normalized;
}

function role(value: unknown): string {
  const normalized = requiredString(value, "role", 32).toLowerCase();
  if (!MEMBERSHIP_ROLES.has(normalized)) invalid(400, "role is invalid");
  return normalized;
}

function uuid(value: unknown, field: string): string {
  const text = requiredString(value, field, 64);
  try {
    return requireUuid(text, field);
  } catch (error) {
    if (error instanceof BrainMembershipError) invalid(error.status, error.message);
    throw error;
  }
}

function bool(value: unknown, field: string): boolean {
  if (typeof value !== "boolean") invalid(400, `${field} must be a boolean`);
  return value;
}

function reason(value: unknown): string | null {
  if (value === undefined || value === null) return null;
  if (typeof value !== "string") invalid(400, "reason must be a string or null");
  const normalized = value.trim();
  if (normalized.length > 512) invalid(400, "reason is too long");
  return normalized || null;
}

function email(value: unknown): string {
  const normalized = requiredString(value, "email", 320).toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized)) invalid(400, "email is invalid");
  return normalized;
}

function grantKey(value: unknown): string {
  const normalized = requiredString(value, "grant_key", 96).toLowerCase();
  if (!KEY_RE.test(normalized)) invalid(400, "grant_key is invalid");
  return normalized;
}

function environment(value: unknown): string {
  const normalized = requiredString(value, "environment", 64).toLowerCase();
  if (!ENVIRONMENT_RE.test(normalized)) invalid(400, "environment is invalid");
  return normalized;
}

function scopes(value: unknown): string[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > 128) {
    invalid(400, "scopes must contain 1-128 values");
  }
  const normalized = [...new Set(value.map((item) => {
    if (typeof item !== "string") invalid(400, "scope must be a string");
    const scope = item.trim();
    if (!SCOPE_RE.test(scope)) invalid(400, "scope is invalid");
    return scope;
  }))].sort();
  if (!normalized.length) invalid(400, "at least one scope is required");
  return normalized;
}

function credentials(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    invalid(400, "credentials must be an object");
  }
  const entries = Object.entries(value as Record<string, unknown>);
  if (entries.length < 1 || entries.length > 16) invalid(400, "credentials must contain 1-16 fields");
  const normalized: Record<string, string> = {};
  for (const [key, raw] of entries) {
    const cleanKey = key.trim();
    if (!cleanKey || cleanKey.length > 128) invalid(400, "credential field name is invalid");
    if (typeof raw !== "string" || !raw || raw.length > 8192) {
      invalid(400, "credential field value is invalid");
    }
    normalized[cleanKey] = raw;
  }
  return normalized;
}

function expiresAt(value: unknown): string | null {
  if (value === undefined || value === null || value === "") return null;
  if (typeof value !== "string" || value.length > 64) invalid(400, "expires_at is invalid");
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) invalid(400, "expires_at is invalid");
  return parsed.toISOString();
}

export function parseAdminCenterAction(value: unknown): AdminCenterAction {
  const base = exactObject(
    value,
    new Set([
      "action",
      "email",
      "role",
      "membership_id",
      "integration_id",
      "provider_id",
      "model_id",
      "service_id",
      "grant_id",
      "grant_key",
      "display_name",
      "owner_user_id",
      "environment",
      "scopes",
      "expires_at",
      "credentials",
      "enabled",
      "reason",
    ]),
    "admin action",
  );
  const action = requiredString(base.action, "action", 64);

  if (action === "member_invite") return { action, email: email(base.email), role: role(base.role) };
  if (action === "member_role") return { action, membership_id: uuid(base.membership_id, "membership_id"), role: role(base.role) };
  if (action === "member_remove") return { action, membership_id: uuid(base.membership_id, "membership_id") };
  if (action === "integration_revoke") return { action, integration_id: uuid(base.integration_id, "integration_id") };
  if (action === "ai_provider_status") return { action, provider_id: uuid(base.provider_id, "provider_id"), enabled: bool(base.enabled, "enabled") };
  if (action === "ai_provider_rotate") return { action, provider_id: uuid(base.provider_id, "provider_id"), credentials: credentials(base.credentials) };
  if (action === "ai_provider_revoke") return { action, provider_id: uuid(base.provider_id, "provider_id") };
  if (action === "ai_model_status") return { action, model_id: uuid(base.model_id, "model_id"), enabled: bool(base.enabled, "enabled") };
  if (action === "api_grant_create") {
    return {
      action,
      service_id: uuid(base.service_id, "service_id"),
      grant_key: grantKey(base.grant_key),
      display_name: requiredString(base.display_name, "display_name", 160),
      owner_user_id: uuid(base.owner_user_id, "owner_user_id"),
      environment: environment(base.environment),
      scopes: scopes(base.scopes),
      expires_at: expiresAt(base.expires_at),
      credentials: credentials(base.credentials),
    };
  }
  if (action === "api_grant_owner") {
    return { action, grant_id: uuid(base.grant_id, "grant_id"), owner_user_id: uuid(base.owner_user_id, "owner_user_id"), reason: reason(base.reason) };
  }
  if (action === "api_grant_scopes") return { action, grant_id: uuid(base.grant_id, "grant_id"), scopes: scopes(base.scopes), reason: reason(base.reason) };
  if (action === "api_grant_environment") return { action, grant_id: uuid(base.grant_id, "grant_id"), environment: environment(base.environment), reason: reason(base.reason) };
  if (action === "api_grant_rotate") return { action, grant_id: uuid(base.grant_id, "grant_id"), credentials: credentials(base.credentials), reason: reason(base.reason) };
  if (action === "api_grant_status") return { action, grant_id: uuid(base.grant_id, "grant_id"), enabled: bool(base.enabled, "enabled"), reason: reason(base.reason) };
  if (action === "api_grant_revoke") return { action, grant_id: uuid(base.grant_id, "grant_id"), reason: reason(base.reason) };
  invalid(400, "Unknown admin action");
}

async function requireAdmin(accessToken: string, organizationId: string): Promise<string> {
  try {
    const organization = await requireBrainOrganizationMembership(accessToken, organizationId);
    if (!ADMIN_ROLES.has(organization.role)) invalid(403, "Admin Center is not available for this role");
    return organization.role;
  } catch (error) {
    if (error instanceof AdminCenterBffError) throw error;
    if (error instanceof BrainMembershipError) throw new AdminCenterBffError(error.status, error.message);
    throw error;
  }
}

export async function handleAdminCenterAction(
  accessToken: string,
  organizationId: string,
  value: unknown,
): Promise<void> {
  const viewerRole = await requireAdmin(accessToken, organizationId);
  const action = parseAdminCenterAction(value);

  if (viewerRole !== "owner") {
    if (
      (action.action === "member_invite" && ["owner", "admin"].includes(action.role))
      || (action.action === "member_role" && ["owner", "admin"].includes(action.role))
    ) {
      invalid(403, "Only owners can assign owner or admin roles");
    }
  }

  switch (action.action) {
    case "member_invite":
      await inviteOrganizationMember(accessToken, organizationId, action.email, action.role);
      return;
    case "member_role":
      await changeOrganizationMemberRole(accessToken, organizationId, action.membership_id, action.role);
      return;
    case "member_remove":
      await removeOrganizationMember(accessToken, organizationId, action.membership_id);
      return;
    case "integration_revoke":
      await revokeIntegration(accessToken, organizationId, action.integration_id);
      return;
    case "ai_provider_status":
      await setAIProviderEnabled(accessToken, organizationId, action.provider_id, action.enabled);
      return;
    case "ai_provider_rotate":
      await rotateAIProviderCredentials(accessToken, organizationId, action.provider_id, action.credentials);
      return;
    case "ai_provider_revoke":
      await revokeAIProvider(accessToken, organizationId, action.provider_id);
      return;
    case "ai_model_status":
      await setAIModelEnabled(accessToken, organizationId, action.model_id, action.enabled);
      return;
    case "api_grant_create":
      await createAPIGrant(accessToken, organizationId, {
        service_id: action.service_id,
        grant_key: action.grant_key,
        display_name: action.display_name,
        owner_user_id: action.owner_user_id,
        environment: action.environment,
        scopes: action.scopes,
        expires_at: action.expires_at,
        credentials: action.credentials,
      });
      return;
    case "api_grant_owner":
      await changeAPIGrantOwner(accessToken, organizationId, action.grant_id, action.owner_user_id, action.reason);
      return;
    case "api_grant_scopes":
      await changeAPIGrantScopes(accessToken, organizationId, action.grant_id, action.scopes, action.reason);
      return;
    case "api_grant_environment":
      await changeAPIGrantEnvironment(accessToken, organizationId, action.grant_id, action.environment, action.reason);
      return;
    case "api_grant_rotate":
      await rotateAPIGrantCredentials(accessToken, organizationId, action.grant_id, action.credentials, action.reason);
      return;
    case "api_grant_status":
      await setAPIGrantEnabled(accessToken, organizationId, action.grant_id, action.enabled, action.reason);
      return;
    case "api_grant_revoke":
      await revokeAPIGrant(accessToken, organizationId, action.grant_id, action.reason);
      return;
  }
}
