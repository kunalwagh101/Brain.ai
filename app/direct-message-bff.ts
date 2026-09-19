import { BrainApiError } from "./brain-api";
import {
  editDirectMessage,
  getDirectMessage,
  listDirectMessages,
  retractDirectMessage,
} from "./direct-message-api";
import { requireBrainOrganizationMembership, requireUuid } from "./brain-membership";

const MESSAGE_ROLES = new Set(["owner", "admin", "executive", "manager", "member"]);
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export class DirectMessageBffError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "DirectMessageBffError";
    this.status = status;
  }
}

function apiBaseUrl(): string {
  const configured = process.env.BRAIN_API_BASE_URL?.trim();
  if (!configured) throw new DirectMessageBffError(503, "Brain API is unavailable");
  const parsed = new URL(configured);
  if (process.env.NODE_ENV === "production" && parsed.protocol !== "https:") {
    throw new DirectMessageBffError(503, "Brain API transport is invalid");
  }
  return configured.replace(/\/$/, "");
}

async function assertMessagingMembership(accessToken: string, organizationId: string) {
  const organization = await requireBrainOrganizationMembership(accessToken, organizationId);
  if (!MESSAGE_ROLES.has(organization.role)) {
    throw new DirectMessageBffError(403, "Direct messaging is unavailable for this role");
  }
}

async function forward<T>(
  accessToken: string,
  path: string,
  body: object,
  headers?: Record<string, string>,
): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    method: "POST",
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      ...headers,
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

export async function handleDirectConversationCreate(
  accessToken: string,
  organizationId: string,
  input: unknown,
): Promise<unknown> {
  await assertMessagingMembership(accessToken, organizationId);
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new DirectMessageBffError(400, "Invalid direct message request");
  }
  const record = input as Record<string, unknown>;
  if (Object.keys(record).some((key) => key !== "target_email")) {
    throw new DirectMessageBffError(400, "Unexpected direct message field");
  }
  const email = typeof record.target_email === "string" ? record.target_email.trim().toLowerCase() : "";
  if (!email || email.length > 320 || !EMAIL_PATTERN.test(email)) {
    throw new DirectMessageBffError(400, "Target email is invalid");
  }
  return forward(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/direct-messages`,
    { target_email: email },
  );
}

export async function handleDirectMessageList(
  accessToken: string,
  organizationId: string,
  conversationId: string,
  limit: number,
  beforeSequence: number | null,
): Promise<unknown> {
  await assertMessagingMembership(accessToken, organizationId);
  requireUuid(conversationId, "conversationId");
  if (!Number.isInteger(limit) || limit < 1 || limit > 200) {
    throw new DirectMessageBffError(400, "Direct-message limit is invalid");
  }
  if (
    beforeSequence !== null
    && (!Number.isInteger(beforeSequence) || beforeSequence < 1)
  ) {
    throw new DirectMessageBffError(400, "Direct-message cursor is invalid");
  }
  return listDirectMessages(
    accessToken,
    organizationId,
    conversationId,
    limit,
    beforeSequence,
  );
}

export async function handleDirectMessageEdit(
  accessToken: string,
  organizationId: string,
  conversationId: string,
  messageId: string,
  input: unknown,
): Promise<unknown> {
  await assertMessagingMembership(accessToken, organizationId);
  requireUuid(conversationId, "conversationId");
  requireUuid(messageId, "messageId");
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new DirectMessageBffError(400, "Invalid direct-message edit request");
  }
  const record = input as Record<string, unknown>;
  if (
    Object.keys(record).some(
      (key) => key !== "body" && key !== "expected_revision",
    )
  ) {
    throw new DirectMessageBffError(400, "Unexpected direct-message edit field");
  }
  const body = typeof record.body === "string" ? record.body.trim() : "";
  const expectedRevision = record.expected_revision;
  if (!body || body.length > 20_000) {
    throw new DirectMessageBffError(400, "Direct-message edit body is invalid");
  }
  if (
    typeof expectedRevision !== "number"
    || !Number.isInteger(expectedRevision)
    || expectedRevision < 1
  ) {
    throw new DirectMessageBffError(400, "Direct-message revision is invalid");
  }
  return editDirectMessage(
    accessToken,
    organizationId,
    conversationId,
    messageId,
    body,
    expectedRevision,
  );
}

export async function handleDirectMessageRetract(
  accessToken: string,
  organizationId: string,
  conversationId: string,
  messageId: string,
  input: unknown,
): Promise<unknown> {
  await assertMessagingMembership(accessToken, organizationId);
  requireUuid(conversationId, "conversationId");
  requireUuid(messageId, "messageId");
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new DirectMessageBffError(400, "Invalid direct-message retract request");
  }
  const record = input as Record<string, unknown>;
  if (Object.keys(record).some((key) => key !== "expected_revision")) {
    throw new DirectMessageBffError(400, "Unexpected direct-message retract field");
  }
  const expectedRevision = record.expected_revision;
  if (
    typeof expectedRevision !== "number"
    || !Number.isInteger(expectedRevision)
    || expectedRevision < 1
  ) {
    throw new DirectMessageBffError(400, "Direct-message revision is invalid");
  }
  return retractDirectMessage(
    accessToken,
    organizationId,
    conversationId,
    messageId,
    expectedRevision,
  );
}

export async function handleDirectMessageRead(
  accessToken: string,
  organizationId: string,
  conversationId: string,
  messageId: string,
): Promise<unknown> {
  await assertMessagingMembership(accessToken, organizationId);
  requireUuid(conversationId, "conversationId");
  requireUuid(messageId, "messageId");
  return getDirectMessage(accessToken, organizationId, conversationId, messageId);
}

export async function handleDirectMessageMarkRead(
  accessToken: string,
  organizationId: string,
  conversationId: string,
  input: unknown,
): Promise<unknown> {
  await assertMessagingMembership(accessToken, organizationId);
  requireUuid(conversationId, "conversationId");
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new DirectMessageBffError(400, "Invalid direct-message read request");
  }
  const record = input as Record<string, unknown>;
  if (Object.keys(record).some((key) => key !== "through_message_id")) {
    throw new DirectMessageBffError(400, "Unexpected direct-message read field");
  }
  const throughMessageId = typeof record.through_message_id === "string"
    ? record.through_message_id
    : "";
  requireUuid(throughMessageId, "through_message_id");
  return forward(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/direct-messages/${encodeURIComponent(conversationId)}/read`,
    { through_message_id: throughMessageId },
  );
}

export async function handleDirectMessageSend(
  accessToken: string,
  organizationId: string,
  conversationId: string,
  input: unknown,
  idempotencyKey: string,
): Promise<unknown> {
  await assertMessagingMembership(accessToken, organizationId);
  requireUuid(conversationId, "conversationId");
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new DirectMessageBffError(400, "Invalid direct message request");
  }
  const record = input as Record<string, unknown>;
  if (Object.keys(record).some((key) => key !== "body")) {
    throw new DirectMessageBffError(400, "Unexpected direct message field");
  }
  const body = typeof record.body === "string" ? record.body.trim() : "";
  if (!body || body.length > 20_000) {
    throw new DirectMessageBffError(400, "Direct message body is invalid");
  }
  const key = idempotencyKey.trim();
  if (!key || key.length > 128) {
    throw new DirectMessageBffError(400, "Idempotency key is invalid");
  }
  return forward(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/direct-messages/${encodeURIComponent(conversationId)}/messages`,
    { body },
    { "Idempotency-Key": key },
  );
}
