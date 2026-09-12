import {
  createNativeChannel,
  sendNativeMessage,
  type NativeChannel,
  type NativeChannelCreateInput,
  type NativeMessage,
} from "./brain-api";
import {
  BrainMembershipError,
  requireBrainOrganizationMembership,
  requireUuid,
} from "./brain-membership";

const CHAT_WRITE_ROLES = new Set(["owner", "admin", "executive", "manager", "member"]);
const IDEMPOTENCY_KEY_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/;

export class NativeChatBffRequestError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "NativeChatBffRequestError";
    this.status = status;
  }
}

function invalid(status: number, message: string): never {
  throw new NativeChatBffRequestError(status, message);
}

function exactObject(value: unknown, allowed: Set<string>, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    invalid(400, `${label} must be an object`);
  }
  const body = value as Record<string, unknown>;
  for (const key of Object.keys(body)) {
    if (!allowed.has(key)) invalid(400, `Unexpected ${label} field: ${key}`);
  }
  return body;
}

function requiredText(value: unknown, field: string, maxLength: number): string {
  if (typeof value !== "string") invalid(400, `${field} must be a string`);
  const normalized = value.trim();
  if (!normalized || normalized.length > maxLength) invalid(400, `${field} is invalid`);
  return normalized;
}

function optionalText(value: unknown, field: string, maxLength: number): string | null | undefined {
  if (value === undefined || value === null) return value;
  if (typeof value !== "string") invalid(400, `${field} must be a string or null`);
  const normalized = value.trim();
  if (normalized.length > maxLength) invalid(400, `${field} is invalid`);
  return normalized || null;
}

function normalizeIdempotencyKey(value: string): string {
  const normalized = value.trim();
  if (!IDEMPOTENCY_KEY_PATTERN.test(normalized)) {
    invalid(400, "Idempotency-Key is invalid");
  }
  return normalized;
}

async function requireChatWriter(accessToken: string, organizationId: string) {
  try {
    const organization = await requireBrainOrganizationMembership(accessToken, organizationId);
    if (!CHAT_WRITE_ROLES.has(organization.role)) {
      invalid(403, "Native chat write is not available for this role");
    }
    return organization;
  } catch (error) {
    if (error instanceof NativeChatBffRequestError) throw error;
    if (error instanceof BrainMembershipError) {
      throw new NativeChatBffRequestError(error.status, error.message);
    }
    throw error;
  }
}

export function parseNativeChannelCreateInput(value: unknown): NativeChannelCreateInput {
  const body = exactObject(
    value,
    new Set(["name", "description", "visibility"]),
    "native channel request",
  );
  const visibility = body.visibility ?? "organization";
  if (visibility !== "organization" && visibility !== "restricted") {
    invalid(400, "visibility must be organization or restricted");
  }
  return {
    name: requiredText(body.name, "name", 160),
    description: optionalText(body.description, "description", 500),
    visibility,
  };
}

export function parseNativeMessageInput(value: unknown): { body: string } {
  const body = exactObject(value, new Set(["body"]), "native message request");
  return { body: requiredText(body.body, "body", 20_000) };
}

export async function handleNativeChannelCreateBff(
  accessToken: string,
  organizationId: string,
  body: unknown,
): Promise<NativeChannel> {
  await requireChatWriter(accessToken, organizationId);
  return createNativeChannel(
    accessToken,
    organizationId,
    parseNativeChannelCreateInput(body),
  );
}

export async function handleNativeMessageCreateBff(
  accessToken: string,
  organizationId: string,
  channelId: string,
  body: unknown,
  idempotencyKey: string,
): Promise<NativeMessage> {
  await requireChatWriter(accessToken, organizationId);
  try {
    requireUuid(channelId, "channelId");
  } catch (error) {
    if (error instanceof BrainMembershipError) {
      throw new NativeChatBffRequestError(error.status, error.message);
    }
    throw error;
  }
  return sendNativeMessage(
    accessToken,
    organizationId,
    channelId,
    parseNativeMessageInput(body),
    normalizeIdempotencyKey(idempotencyKey),
  );
}
