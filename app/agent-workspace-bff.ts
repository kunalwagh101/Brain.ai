import {
  advanceAgentWorkspaceRun,
  cancelAgentWorkspaceRun,
  createAgentWorkspaceRun,
  decideAgentWorkspaceStep,
  getAgentWorkspaceRun,
  type AgentWorkspaceRun,
  type AgentWorkspaceRunInput,
} from "./agent-workspace-api";
import {
  BrainMembershipError,
  requireBrainOrganizationMembership,
  requireUuid,
} from "./brain-membership";

const AGENT_USE_ROLES = new Set(["owner", "admin", "executive", "manager", "member"]);

export class AgentWorkspaceBffError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "AgentWorkspaceBffError";
    this.status = status;
  }
}

function invalid(status: number, message: string): never {
  throw new AgentWorkspaceBffError(status, message);
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

function optionalUuid(value: unknown, field: string): string | null | undefined {
  if (value === undefined || value === null) return value;
  if (typeof value !== "string") invalid(400, `${field} must be a UUID or null`);
  try {
    return requireUuid(value, field);
  } catch (error) {
    if (error instanceof BrainMembershipError) invalid(error.status, error.message);
    throw error;
  }
}

function requiredUuid(value: unknown, field: string): string {
  const text = requiredText(value, field, 64);
  try {
    return requireUuid(text, field);
  } catch (error) {
    if (error instanceof BrainMembershipError) invalid(error.status, error.message);
    throw error;
  }
}

async function requireAgentUser(accessToken: string, organizationId: string) {
  try {
    const organization = await requireBrainOrganizationMembership(accessToken, organizationId);
    if (!AGENT_USE_ROLES.has(organization.role)) {
      invalid(403, "Agent workspace is not available for this role");
    }
    return organization;
  } catch (error) {
    if (error instanceof AgentWorkspaceBffError) throw error;
    if (error instanceof BrainMembershipError) {
      throw new AgentWorkspaceBffError(error.status, error.message);
    }
    throw error;
  }
}

export function parseAgentWorkspaceRunInput(value: unknown): AgentWorkspaceRunInput {
  const body = exactObject(
    value,
    new Set(["agent_definition_id", "objective", "project_node_id", "native_channel_id"]),
    "agent workspace run request",
  );
  const projectId = optionalUuid(body.project_node_id, "project_node_id");
  const channelId = optionalUuid(body.native_channel_id, "native_channel_id");
  if (!projectId && !channelId) {
    invalid(400, "A visible project or Brain channel context is required");
  }
  return {
    agent_definition_id: requiredUuid(body.agent_definition_id, "agent_definition_id"),
    objective: requiredText(body.objective, "objective", 20_000),
    ...(projectId === undefined ? {} : { project_node_id: projectId }),
    ...(channelId === undefined ? {} : { native_channel_id: channelId }),
  };
}

export function parseAdvanceInput(value: unknown): { objective: string } {
  const body = exactObject(value, new Set(["objective"]), "agent advance request");
  return { objective: requiredText(body.objective, "objective", 20_000) };
}

export function parseApprovalInput(value: unknown): { approve: boolean; reason: string | null } {
  const body = exactObject(value, new Set(["approve", "reason"]), "agent approval request");
  if (typeof body.approve !== "boolean") invalid(400, "approve must be a boolean");
  let reason: string | null = null;
  if (body.reason !== undefined && body.reason !== null) {
    if (typeof body.reason !== "string") invalid(400, "reason must be a string or null");
    const normalized = body.reason.trim();
    if (normalized.length > 500) invalid(400, "reason is too long");
    reason = normalized || null;
  }
  return { approve: body.approve, reason };
}

export async function handleAgentWorkspaceStart(
  accessToken: string,
  organizationId: string,
  value: unknown,
): Promise<AgentWorkspaceRun> {
  await requireAgentUser(accessToken, organizationId);
  return createAgentWorkspaceRun(
    accessToken,
    organizationId,
    parseAgentWorkspaceRunInput(value),
  );
}

export async function handleAgentWorkspaceAdvance(
  accessToken: string,
  organizationId: string,
  runId: string,
  value: unknown,
): Promise<AgentWorkspaceRun> {
  await requireAgentUser(accessToken, organizationId);
  requiredUuid(runId, "runId");
  const { objective } = parseAdvanceInput(value);
  await advanceAgentWorkspaceRun(accessToken, organizationId, runId, objective);
  return getAgentWorkspaceRun(accessToken, organizationId, runId);
}

export async function handleAgentWorkspaceApproval(
  accessToken: string,
  organizationId: string,
  runId: string,
  stepId: string,
  value: unknown,
): Promise<AgentWorkspaceRun> {
  await requireAgentUser(accessToken, organizationId);
  requiredUuid(runId, "runId");
  requiredUuid(stepId, "stepId");
  const input = parseApprovalInput(value);
  await decideAgentWorkspaceStep(
    accessToken,
    organizationId,
    runId,
    stepId,
    input.approve,
    input.reason,
  );
  return getAgentWorkspaceRun(accessToken, organizationId, runId);
}

export async function handleAgentWorkspaceCancel(
  accessToken: string,
  organizationId: string,
  runId: string,
): Promise<AgentWorkspaceRun> {
  await requireAgentUser(accessToken, organizationId);
  requiredUuid(runId, "runId");
  await cancelAgentWorkspaceRun(accessToken, organizationId, runId);
  return getAgentWorkspaceRun(accessToken, organizationId, runId);
}
