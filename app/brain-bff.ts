import {
  askBrain,
  type AskBrainInput,
  type AskBrainResponse,
} from "./brain-api";
import {
  BrainMembershipError,
  requireBrainOrganizationMembership,
  requireUuid,
} from "./brain-membership";

export class BrainBffRequestError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "BrainBffRequestError";
    this.status = status;
  }
}

function invalid(message: string): never {
  throw new BrainBffRequestError(400, message);
}

function requiredString(value: unknown, field: string, maxLength: number): string {
  if (typeof value !== "string") invalid(`${field} must be a string`);
  const normalized = value.trim();
  if (!normalized || normalized.length > maxLength) invalid(`${field} is invalid`);
  return normalized;
}

function requiredUuid(value: unknown, field: string): string {
  const normalized = requiredString(value, field, 64);
  try {
    return requireUuid(normalized, field);
  } catch (error) {
    if (error instanceof BrainMembershipError) invalid(error.message);
    throw error;
  }
}

export function parseAskBrainBffInput(value: unknown): AskBrainInput {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    invalid("Ask Brain request must be an object");
  }

  const body = value as Record<string, unknown>;
  const allowed = new Set([
    "question",
    "provider_configuration_id",
    "model_configuration_id",
    "search_mode",
    "search_limit",
    "max_output_tokens",
    "attribution_node_id",
  ]);
  for (const key of Object.keys(body)) {
    if (!allowed.has(key)) invalid(`Unexpected Ask Brain field: ${key}`);
  }

  const searchMode = body.search_mode ?? "hybrid";
  if (searchMode !== "keyword" && searchMode !== "hybrid") {
    invalid("search_mode must be keyword or hybrid");
  }

  const searchLimit = body.search_limit ?? 8;
  if (
    typeof searchLimit !== "number"
    || !Number.isInteger(searchLimit)
    || searchLimit < 1
    || searchLimit > 8
  ) {
    invalid("search_limit must be an integer from 1 to 8");
  }

  const maxOutputTokens = body.max_output_tokens;
  if (
    maxOutputTokens !== undefined
    && (
      typeof maxOutputTokens !== "number"
      || !Number.isInteger(maxOutputTokens)
      || maxOutputTokens < 1
      || maxOutputTokens > 8192
    )
  ) {
    invalid("max_output_tokens must be an integer from 1 to 8192");
  }

  const attribution = body.attribution_node_id;
  if (attribution !== undefined && attribution !== null && typeof attribution !== "string") {
    invalid("attribution_node_id must be a UUID or null");
  }

  return {
    question: requiredString(body.question, "question", 2000),
    provider_configuration_id: requiredUuid(
      body.provider_configuration_id,
      "provider_configuration_id",
    ),
    model_configuration_id: requiredUuid(
      body.model_configuration_id,
      "model_configuration_id",
    ),
    search_mode: searchMode,
    search_limit: searchLimit,
    ...(maxOutputTokens === undefined ? {} : { max_output_tokens: maxOutputTokens }),
    ...(attribution === undefined
      ? {}
      : {
          attribution_node_id:
            attribution === null ? null : requiredUuid(attribution, "attribution_node_id"),
        }),
  };
}

export async function handleAskBrainBff(
  accessToken: string,
  organizationId: string,
  body: unknown,
): Promise<AskBrainResponse> {
  try {
    await requireBrainOrganizationMembership(accessToken, organizationId);
  } catch (error) {
    if (error instanceof BrainMembershipError) {
      throw new BrainBffRequestError(error.status, error.message);
    }
    throw error;
  }

  return askBrain(accessToken, organizationId, parseAskBrainBffInput(body));
}
