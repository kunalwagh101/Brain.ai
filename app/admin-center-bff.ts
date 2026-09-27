import {
  changeAPIGrantEnvironment,
  changeAPIGrantOwner,
  changeAPIGrantScopes,
  changeOrganizationMemberRole,
  createAIModel,
  createAIProvider,
  createAPIGrant,
  createAPIService,
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
const SERVICE_KEY_RE = /^[a-z0-9][a-z0-9._-]{0,63}$/;
const ENVIRONMENT_RE = /^[a-z0-9][a-z0-9._-]{0,63}$/;
const SCOPE_RE = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/;
const MODEL_KEY_RE = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$/;
const AI_ADAPTER_KINDS = new Set(["openai_chat_completions"]);

export type AdminCenterAction =
  | { action: "member_invite"; email: string; role: string }
  | { action: "member_role"; membership_id: string; role: string }
  | { action: "member_remove"; membership_id: string }
  | { action: "integration_revoke"; integration_id: string }
  | {
      action: "ai_provider_create";
      provider_key: string;
      display_name: string;
      adapter_kind: string;
      api_url: string;
      credentials: Record<string, string>;
    }
  | { action: "ai_provider_status"; provider_id: string; enabled: boolean }
  | { action: "ai_provider_rotate"; provider_id: string; credentials: Record<string, string> }
  | { action: "ai_provider_revoke"; provider_id: string }
  | {
      action: "ai_model_create";
      provider_id: string;
      model_key: string;
      display_name: string;
      enabled: boolean;
      max_output_tokens: number | null;
    }
  | { action: "ai_model_status"; model_id: string; enabled: boolean }
  | {
      action: "api_service_create";
      service_key: string;
      display_name: string;
      provider_name: string;
      base_url: string | null;
    }
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

function optionalString(value: unknown, field: string, maxLength: number): string | null {
  if (value === undefined || value === null || value === "") return null;
  if (typeof value !== "string") invalid(400, `${field} must be a string or null`);
  const normalized = value.trim();
  if (normalized.length > maxLength) invalid(400, `${field} is invalid`);
  return normalized || null;
}

function normalizedKey(value: unknown, field: string, maxLength: number, pattern: RegExp): string {
  const normalized = requiredString(value, field, maxLength).toLowerCase();
  if (!pattern.test(normalized)) invalid(400, `${field} is invalid`);
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

function nullablePositiveInt(value: unknown, field: string, max: number): number | null {
  if (value === undefined || value === null || value === "") return null;
  if (typeof value !== "number" || !Number.isInteger(value) || value < 1 || value > max) {
    invalid(400, `${field} is invalid`);
  }
  return value;
}

function reason(value: unknown): string | null {
  return optionalString(value, "reason", 512);
}

function email(value: unknown): string {
  const normalized = requiredString(value, "email", 320).toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized)) invalid(400, "email is invalid");
  return normalized;
}

function environment(value: unknown): string {
  return normalizedKey(value, "environment", 64, ENVIRONMENT_RE);
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
  if (!value || typeof value !== "object" || Array.isArray(value)) invalid(400, "credentials must be an object");
  const entries = Object.entries(value as Record<string, unknown>);
  if (entries.length < 1 || entries.length > 16) invalid(400, "credentials must contain 1-16 fields");
  const normalized: Record<string, string> = {};
  for (const [key, raw] of entries) {
    const cleanKey = key.trim();
    if (!cleanKey || cleanKey.length > 128) invalid(400, "credential field name is invalid");
    if (typeof raw !== "string" || !raw || raw.length > 8192) invalid(400, "credential field value is invalid");
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

function httpUrl(value: unknown, field: string, nullable = false): string | null {
  const text = nullable ? optionalString(value, field, 2048) : requiredString(value, field, 2048);
  if (text === null) return null;
  try {
    const parsed = new URL(text);
    if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password || parsed.hash) throw new Error();
  } catch {
    invalid(400, `${field} is invalid`);
  }
  return text;
}

export function parseAdminCenterAction(value: unknown): AdminCenterAction {
  const base = exactObject(
    value,
    new Set([
      "action", "email", "role", "membership_id", "integration_id", "provider_id", "model_id",
      "provider_key", "adapter_kind", "api_url", "model_key", "max_output_tokens",
      "service_id", "service_key", "provider_name", "base_url", "grant_id", "grant_key",
      "display_name", "owner_user_id", "environment", "scopes", "expires_at", "credentials",
      "enabled", "reason",
    ]),
    "admin action",
  );
  const action = requiredString(base.action, "action", 64);

  if (action === "member_invite") return { action, email: email(base.email), role: role(base.role) };
  if (action === "member_role") return { action, membership_id: uuid(base.membership_id, "membership_id"), role: role(base.role) };
  if (action === "member_remove") return { action, membership_id: uuid(base.membership_id, "membership_id") };
  if (action === "integration_revoke") return { action, integration_id: uuid(base.integration_id, "integration_id") };
  if (action === "ai_provider_create") {
    const adapterKind = requiredString(base.adapter_kind, "adapter_kind", 48);
    if (!AI_ADAPTER_KINDS.has(adapterKind)) invalid(400, "adapter_kind is invalid");
    return {
      action,
      provider_key: normalizedKey(base.provider_key, "provider_key", 64, SERVICE_KEY_RE),
      display_name: requiredString(base.display_name, "display_name", 160),
      adapter_kind: adapterKind,
      api_url: httpUrl(base.api_url, "api_url") as string,
      credentials: credentials(base.credentials),
    };
  }
  if (action === "ai_provider_status") return { action, provider_id: uuid(base.provider_id, "provider_id"), enabled: bool(base.enabled, "enabled") };
  if (action === "ai_provider_rotate") return { action, provider_id: uuid(base.provider_id, "provider_id"), credentials: credentials(base.credentials) };
  if (action === "ai_provider_revoke") return { action, provider_id: uuid(base.provider_id, "provider_id") };
  if (action === "ai_model_create") {
    const modelKey = requiredString(base.model_key, "model_key", 255);
    if (!MODEL_KEY_RE.test(modelKey)) invalid(400, "model_key is invalid");
    return {
      action,
      provider_id: uuid(base.provider_id, "provider_id"),
      model_key: modelKey,
      display_name: requiredString(base.display_name, "display_name", 255),
      enabled: base.enabled === undefined ? true : bool(base.enabled, "enabled"),
      max_output_tokens: nullablePositiveInt(base.max_output_tokens, "max_output_tokens", 1_000_000),
    };
  }
  if (action === "ai_model_status") return { action, model_id: uuid(base.model_id, "model_id"), enabled: bool(base.enabled, "enabled") };
  if (action === "api_service_create") {
    return {
      action,
      service_key: normalizedKey(base.service_key, "service_key", 64, SERVICE_KEY_RE),
      display_name: requiredString(base.display_name, "display_name", 160),
      provider_name: requiredString(base.provider_name, "provider_name", 160),
      base_url: httpUrl(base.base_url, "base_url", true),
    };
  }
  if (action === "api_grant_create") {
    return {
      action,
      service_id: uuid(base.service_id, "service_id"),
      grant_key: normalizedKey(base.grant_key, "grant_key", 96, KEY_RE),
      display_name: requiredString(base.display_name, "display_name", 160),
      owner_user_id: uuid(base.owner_user_id, "owner_user_id"),
      environment: environment(base.environment),
      scopes: scopes(base.scopes),
      expires_at: expiresAt(base.expires_at),
      credentials: credentials(base.credentials),
    };
  }
  if (action === "api_grant_owner") return { action, grant_id: uuid(base.grant_id, "grant_id"), owner_user_id: uuid(base.owner_user_id, "owner_user_id"), reason: reason(base.reason) };
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

export async function handleAdminCenterAction(accessToken: string, organizationId: string, value: unknown): Promise<void> {
  const viewerRole = await requireAdmin(accessToken, organizationId);
  const action = parseAdminCenterAction(value);

  if (viewerRole !== "owner" && (
    (action.action === "member_invite" && ["owner", "admin"].includes(action.role))
    || (action.action === "member_role" && ["owner", "admin"].includes(action.role))
  )) invalid(403, "Only owners can assign owner or admin roles");

  switch (action.action) {
    case "member_invite": await inviteOrganizationMember(accessToken, organizationId, action.email, action.role); return;
    case "member_role": await changeOrganizationMemberRole(accessToken, organizationId, action.membership_id, action.role); return;
    case "member_remove": await removeOrganizationMember(accessToken, organizationId, action.membership_id); return;
    case "integration_revoke": await revokeIntegration(accessToken, organizationId, action.integration_id); return;
    case "ai_provider_create":
      await createAIProvider(accessToken, organizationId, { provider_key: action.provider_key, display_name: action.display_name, adapter_kind: action.adapter_kind, api_url: action.api_url, credentials: action.credentials }); return;
    case "ai_provider_status": await setAIProviderEnabled(accessToken, organizationId, action.provider_id, action.enabled); return;
    case "ai_provider_rotate": await rotateAIProviderCredentials(accessToken, organizationId, action.provider_id, action.credentials); return;
    case "ai_provider_revoke": await revokeAIProvider(accessToken, organizationId, action.provider_id); return;
    case "ai_model_create": await createAIModel(accessToken, organizationId, action.provider_id, { model_key: action.model_key, display_name: action.display_name, enabled: action.enabled, max_output_tokens: action.max_output_tokens }); return;
    case "ai_model_status": await setAIModelEnabled(accessToken, organizationId, action.model_id, action.enabled); return;
    case "api_service_create": await createAPIService(accessToken, organizationId, { service_key: action.service_key, display_name: action.display_name, provider_name: action.provider_name, base_url: action.base_url }); return;
    case "api_grant_create": await createAPIGrant(accessToken, organizationId, { service_id: action.service_id, grant_key: action.grant_key, display_name: action.display_name, owner_user_id: action.owner_user_id, environment: action.environment, scopes: action.scopes, expires_at: action.expires_at, credentials: action.credentials }); return;
    case "api_grant_owner": await changeAPIGrantOwner(accessToken, organizationId, action.grant_id, action.owner_user_id, action.reason); return;
    case "api_grant_scopes": await changeAPIGrantScopes(accessToken, organizationId, action.grant_id, action.scopes, action.reason); return;
    case "api_grant_environment": await changeAPIGrantEnvironment(accessToken, organizationId, action.grant_id, action.environment, action.reason); return;
    case "api_grant_rotate": await rotateAPIGrantCredentials(accessToken, organizationId, action.grant_id, action.credentials, action.reason); return;
    case "api_grant_status": await setAPIGrantEnabled(accessToken, organizationId, action.grant_id, action.enabled, action.reason); return;
    case "api_grant_revoke": await revokeAPIGrant(accessToken, organizationId, action.grant_id, action.reason); return;
  }
}
