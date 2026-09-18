import {
  createNativeChannel,
  editNativeMessage,
  inviteNativeChannelMember,
  listNativeReplies,
  markNativeChannelRead,
  retractNativeMessage,
  revokeNativeChannelMember,
  sendNativeMessage,
  sendNativeReply,
  setNativeReaction,
  uploadNativeChannelAttachment,
  type NativeAttachment,
  type NativeChannel,
  type NativeChannelCreateInput,
  type NativeChannelMember,
  type NativeChannelUnread,
  type NativeMessage,
  type NativeReaction,
} from "./brain-api";
import {
  BrainMembershipError,
  requireBrainOrganizationMembership,
  requireUuid,
} from "./brain-membership";

const CHAT_WRITE_ROLES = new Set(["owner", "admin", "executive", "manager", "member"]);
const IDEMPOTENCY_KEY_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const ALLOWED_REACTIONS = new Set(["👍", "❤️", "🎉", "👀", "✅"]);
export const MAX_NATIVE_ATTACHMENT_MULTIPART_BYTES = 10_500_000;

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

function normalizedUuid(value: string, field: string): string {
  try {
    return requireUuid(value, field);
  } catch (error) {
    if (error instanceof BrainMembershipError) {
      throw new NativeChatBffRequestError(error.status, error.message);
    }
    throw error;
  }
}

function normalizeMultipartContentType(value: string): string {
  const normalized = value.trim();
  if (!/^multipart\/form-data\s*;/i.test(normalized) || !/boundary=/i.test(normalized)) {
    invalid(415, "Attachment upload must use multipart/form-data with a boundary");
  }
  return normalized;
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

async function requireChatReader(accessToken: string, organizationId: string) {
  try {
    return await requireBrainOrganizationMembership(accessToken, organizationId);
  } catch (error) {
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

export function parseNativeMessageInput(value: unknown): {
  body: string;
  attachment_source_ids: string[];
} {
  const body = exactObject(
    value,
    new Set(["body", "attachment_source_ids"]),
    "native message request",
  );
  const rawBody = body.body ?? "";
  if (typeof rawBody !== "string") invalid(400, "body must be a string");
  const normalizedBody = rawBody.trim();
  if (normalizedBody.length > 20_000) invalid(400, "body is invalid");

  const rawAttachments = body.attachment_source_ids ?? [];
  if (!Array.isArray(rawAttachments) || rawAttachments.length > 5) {
    invalid(400, "attachment_source_ids must contain at most five IDs");
  }
  const attachmentIds = rawAttachments.map((value, index) => {
    if (typeof value !== "string") {
      invalid(400, `attachment_source_ids[${index}] must be a UUID`);
    }
    return normalizedUuid(value, `attachment_source_ids[${index}]`);
  });
  const uniqueAttachmentIds = [...new Set(attachmentIds)];
  if (!normalizedBody && !uniqueAttachmentIds.length) {
    invalid(400, "A message needs text or at least one attachment");
  }
  return {
    body: normalizedBody,
    attachment_source_ids: uniqueAttachmentIds,
  };
}

export function parseNativeMessageEditInput(value: unknown): {
  body: string;
  expected_revision: number;
} {
  const body = exactObject(
    value,
    new Set(["body", "expected_revision"]),
    "native message edit request",
  );
  const expectedRevision = body.expected_revision;
  if (
    typeof expectedRevision !== "number"
    || !Number.isInteger(expectedRevision)
    || expectedRevision < 1
  ) {
    invalid(400, "expected_revision must be a positive integer");
  }
  return {
    body: requiredText(body.body, "body", 20_000),
    expected_revision: expectedRevision,
  };
}

export function parseNativeMessageRetractInput(value: unknown): {
  expected_revision: number;
} {
  const body = exactObject(
    value,
    new Set(["expected_revision"]),
    "native message retract request",
  );
  const expectedRevision = body.expected_revision;
  if (
    typeof expectedRevision !== "number"
    || !Number.isInteger(expectedRevision)
    || expectedRevision < 1
  ) {
    invalid(400, "expected_revision must be a positive integer");
  }
  return { expected_revision: expectedRevision };
}

export function parseNativeMemberInvite(value: unknown): {
  email: string;
  access: "read" | "write";
} {
  const body = exactObject(
    value,
    new Set(["email", "access"]),
    "native channel member request",
  );
  const email = requiredText(body.email, "email", 320).toLowerCase();
  if (!EMAIL_PATTERN.test(email)) invalid(400, "email is invalid");
  const access = body.access ?? "read";
  if (access !== "read" && access !== "write") {
    invalid(400, "access must be read or write");
  }
  return { email, access };
}

export function parseNativeReactionInput(value: unknown): { reaction: string } {
  const body = exactObject(value, new Set(["reaction"]), "native reaction request");
  const reaction = requiredText(body.reaction, "reaction", 32);
  if (!ALLOWED_REACTIONS.has(reaction)) invalid(400, "reaction is not allowed");
  return { reaction };
}

export function parseNativeReadInput(value: unknown): { through_message_id: string } {
  const body = exactObject(
    value,
    new Set(["through_message_id"]),
    "native read request",
  );
  return {
    through_message_id: normalizedUuid(
      requiredText(body.through_message_id, "through_message_id", 36),
      "through_message_id",
    ),
  };
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

export async function handleNativeAttachmentUploadBff(
  accessToken: string,
  organizationId: string,
  channelId: string,
  body: Uint8Array,
  contentType: string,
  idempotencyKey: string,
): Promise<NativeAttachment> {
  await requireChatWriter(accessToken, organizationId);
  normalizedUuid(channelId, "channelId");
  if (!body.byteLength || body.byteLength > MAX_NATIVE_ATTACHMENT_MULTIPART_BYTES) {
    invalid(413, "Attachment upload body is too large");
  }
  return uploadNativeChannelAttachment(
    accessToken,
    organizationId,
    channelId,
    body,
    normalizeMultipartContentType(contentType),
    normalizeIdempotencyKey(idempotencyKey),
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
  normalizedUuid(channelId, "channelId");
  return sendNativeMessage(
    accessToken,
    organizationId,
    channelId,
    parseNativeMessageInput(body),
    normalizeIdempotencyKey(idempotencyKey),
  );
}

export async function handleNativeMessageEditBff(
  accessToken: string,
  organizationId: string,
  channelId: string,
  messageId: string,
  body: unknown,
): Promise<NativeMessage> {
  await requireChatWriter(accessToken, organizationId);
  normalizedUuid(channelId, "channelId");
  normalizedUuid(messageId, "messageId");
  const input = parseNativeMessageEditInput(body);
  return editNativeMessage(
    accessToken,
    organizationId,
    channelId,
    messageId,
    input.body,
    input.expected_revision,
  );
}

export async function handleNativeMessageRetractBff(
  accessToken: string,
  organizationId: string,
  channelId: string,
  messageId: string,
  body: unknown,
): Promise<NativeMessage> {
  await requireChatWriter(accessToken, organizationId);
  normalizedUuid(channelId, "channelId");
  normalizedUuid(messageId, "messageId");
  const input = parseNativeMessageRetractInput(body);
  return retractNativeMessage(
    accessToken,
    organizationId,
    channelId,
    messageId,
    input.expected_revision,
  );
}

export async function handleNativeMemberInviteBff(
  accessToken: string,
  organizationId: string,
  channelId: string,
  body: unknown,
): Promise<NativeChannelMember> {
  await requireChatWriter(accessToken, organizationId);
  normalizedUuid(channelId, "channelId");
  const input = parseNativeMemberInvite(body);
  return inviteNativeChannelMember(
    accessToken,
    organizationId,
    channelId,
    input.email,
    input.access,
  );
}

export async function handleNativeMemberRevokeBff(
  accessToken: string,
  organizationId: string,
  channelId: string,
  userId: string,
): Promise<void> {
  await requireChatWriter(accessToken, organizationId);
  normalizedUuid(channelId, "channelId");
  normalizedUuid(userId, "userId");
  return revokeNativeChannelMember(
    accessToken,
    organizationId,
    channelId,
    userId,
  );
}


export async function handleNativeThreadListBff(
  accessToken: string,
  organizationId: string,
  channelId: string,
  rootMessageId: string,
): Promise<NativeMessage[]> {
  await requireChatReader(accessToken, organizationId);
  normalizedUuid(channelId, "channelId");
  normalizedUuid(rootMessageId, "rootMessageId");
  return listNativeReplies(accessToken, organizationId, channelId, rootMessageId);
}

export async function handleNativeReplyCreateBff(
  accessToken: string,
  organizationId: string,
  channelId: string,
  rootMessageId: string,
  body: unknown,
  idempotencyKey: string,
): Promise<NativeMessage> {
  await requireChatWriter(accessToken, organizationId);
  normalizedUuid(channelId, "channelId");
  normalizedUuid(rootMessageId, "rootMessageId");
  return sendNativeReply(
    accessToken,
    organizationId,
    channelId,
    rootMessageId,
    parseNativeMessageInput(body),
    normalizeIdempotencyKey(idempotencyKey),
  );
}

export async function handleNativeReactionBff(
  accessToken: string,
  organizationId: string,
  channelId: string,
  messageId: string,
  body: unknown,
  active: boolean,
): Promise<NativeReaction | void> {
  await requireChatWriter(accessToken, organizationId);
  normalizedUuid(channelId, "channelId");
  normalizedUuid(messageId, "messageId");
  const { reaction } = parseNativeReactionInput(body);
  return setNativeReaction(
    accessToken,
    organizationId,
    channelId,
    messageId,
    reaction,
    active,
  );
}

export async function handleNativeReadBff(
  accessToken: string,
  organizationId: string,
  channelId: string,
  body: unknown,
): Promise<NativeChannelUnread> {
  await requireChatReader(accessToken, organizationId);
  normalizedUuid(channelId, "channelId");
  const { through_message_id } = parseNativeReadInput(body);
  return markNativeChannelRead(
    accessToken,
    organizationId,
    channelId,
    through_message_id,
  );
}
