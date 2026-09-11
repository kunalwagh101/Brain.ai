import { askBrain, type AskBrainInput, type AskBrainResponse } from "./brain-api";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function requiredString(value: unknown, field: string, maxLength: number): string {
  if (typeof value !== "string") throw new Error(`${field} must be a string`);
  const normalized = value.trim();
  if (!normalized || normalized.length > maxLength) {
    throw new Error(`${field} is invalid`);
  }
  return normalized;
}

function requiredUuid(value: unknown, field: string): string {
  const normalized = requiredString(value, field, 64);
  if (!UUID_PATTERN.test(normalized)) throw new Error(`${field} must be a UUID`);
  return normalized;
}

export function parseAskBrainBffInput(value: unknown): AskBrainInput {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Ask Brain request must be an object");
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
    if (!allowed.has(key)) throw new Error(`Unexpected Ask Brain field: ${key}`);
  }

  const searchMode = body.search_mode ?? "hybrid";
  if (searchMode !== "keyword" && searchMode !== "hybrid") {
    throw new Error("search_mode must be keyword or hybrid");
  }

  const searchLimit = body.search_limit ?? 8;
  if (!Number.isInteger(searchLimit) || Number(searchLimit) < 1 || Number(searchLimit) > 8) {
    throw new Error("search_limit must be an integer from 1 to 8");
  }

  const maxOutputTokens = body.max_output_tokens;
  if (
    maxOutputTokens !== undefined
    && (!Number.isInteger(maxOutputTokens) || Number(maxOutputTokens) < 1 || Number(maxOutputTokens) > 8192)
  ) {
    throw new Error("max_output_tokens must be an integer from 1 to 8192");
  }

  const attribution = body.attribution_node_id;
  if (attribution !== undefined && attribution !== null && typeof attribution !== "string") {
    throw new Error("attribution_node_id must be a UUID or null");
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
    search_limit: Number(searchLimit),
    ...(maxOutputTokens === undefined ? {} : { max_output_tokens: Number(maxOutputTokens) }),
    ...(attribution === undefined
      ? {}
      : { attribution_node_id: attribution === null ? null : requiredUuid(attribution, "attribution_node_id") }),
  };
}

export async function handleAskBrainBff(
  accessToken: string,
  organizationId: string,
  body: unknown,
): Promise<AskBrainResponse> {
  if (!UUID_PATTERN.test(organizationId)) throw new Error("organizationId must be a UUID");
  return askBrain(accessToken, organizationId, parseAskBrainBffInput(body));
}
