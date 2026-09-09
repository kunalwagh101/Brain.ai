# Ask Brain — Evidence-backed RAG

## Purpose

`S-05.02.01` answers a company question only from evidence that the current user is already allowed to retrieve.

The implementation is deliberately provider-neutral. The caller supplies an enabled provider/model configuration from the governed AI gateway. Brain does not choose a production model while `OQ-005` is unresolved.

## Request path

`POST /api/v1/organizations/{organization_id}/ask-brain`

The caller needs `ai.use`. The request supplies:

- `question`
- `provider_configuration_id`
- `model_configuration_id`
- optional search mode, output-token limit and Work Graph attribution node

No global/default provider is guessed.

## Data flow

1. Normalize and validate the question.
2. Run the existing permission-aware search for the authenticated Brain user.
3. Filter revoked/inactive sources inside the search query before document content is selected.
4. Bound the context to at most 8 authorised evidence records and 48,000 evidence characters.
5. If no authorised evidence remains, return `insufficient_evidence` without calling any AI provider.
6. Send the question plus server-assigned evidence IDs (`E1`...`E8`) through the governed AI gateway.
7. Treat source evidence as untrusted data and instruct the model never to execute instructions contained inside it.
8. Accept only structured JSON claims. Every claim must contain one or more evidence IDs supplied by the server.
9. Reject malformed output, empty citations or unknown citations with a 502 response. Ungrounded provider text is never returned to the user.
10. Return only citations actually used by accepted claims, including a bounded excerpt from the exact authorised evidence context sent to the model.

## Grounding contract

Accepted provider output:

```json
{
  "status": "answer",
  "claims": [
    {
      "text": "The authentication middleware was merged.",
      "citations": ["E1"]
    }
  ],
  "uncertainty": null
}
```

No-answer output:

```json
{
  "status": "insufficient_evidence",
  "claims": [],
  "uncertainty": "The available evidence does not establish deployment status."
}
```

The server renders accepted claims into an answer such as:

`The authentication middleware was merged. [E1]`

Each returned citation includes source/provenance identifiers plus an evidence excerpt capped at 800 characters. The excerpt comes from the same already-authorised bounded text supplied to the model; Brain does not perform a wider second fetch to build citations.

This guarantees citation *presence and provenance*. It does not by itself prove semantic entailment (that the cited evidence truly supports the claim). The production model must still pass the labelled citation-correctness evaluation gate.

## Security

- Tenant and live source authorization are reused from `app.search`; no second ACL implementation exists.
- Revoked integration connections are excluded before retrieval.
- AI provider credentials remain in the configured secret store and never enter Ask Brain code.
- Provider/model IDs are tenant-scoped and validated by the AI gateway.
- Budget hard-stops, provider revocation and Work Graph attribution checks are inherited from the AI gateway.
- Prompt and completion bodies are not persisted in `AIRequestRecord`; only governed request metadata is retained.
- Retrieved evidence is bounded to reduce prompt-amplification and cost risk.
- Citation excerpts are bounded and derived only from already-authorised retrieved evidence.
- Provider output is parsed as data and fails closed on invalid grounding.

## Failure behaviour

| Failure | Behaviour |
|---|---|
| Empty/whitespace question | 400 before provider access |
| No authorised matching evidence | 200 + `insufficient_evidence`; no provider call |
| Embedding provider unavailable | search degrades to keyword; `semantic_status` reports degradation |
| AI provider/model disabled or invalid | existing gateway error; no bypass |
| AI budget exhausted | 429 |
| Provider timeout/rate limit/failure | safe 503/429 with request ID |
| Malformed or uncited model output | 502 `invalid_model_output`; no raw output returned |
| Revoked source | excluded by live retrieval predicate |

## Persistence and rollback

This slice adds no database table or migration. Answers are transient. Existing `AIRequestRecord` metadata remains the audit/cost record for provider calls.

Rollback is therefore code-only: remove the Ask Brain route/service. Search documents, raw/canonical evidence and AI gateway records remain unchanged.

## Evaluation gates

Engineering tests cover:

- no-evidence no-call behaviour
- authorised evidence and citation resolution
- bounded citation excerpts
- unknown/missing citation rejection
- cross-tenant evidence exclusion
- revoked-source exclusion
- explicit model no-answer
- guest authorization rejection
- whitespace/client-error behaviour before provider access
- deterministic evaluation-metric gates

Production acceptance still requires:

- retrieval recall >= 90%
- a labelled, representative real-provider Ask Brain evaluation with citation correctness >= 98%
- zero forbidden evidence exposures in labelled permission cases
- staging p95 latency/cost capture for the selected provider/model
- manual UAT against real connected customer evidence

The reproducible deployed evaluator and label contract are documented in `docs/ASK_BRAIN_EVALUATION.md`.

Until those measurements exist, `S-05.02.01` must not be marked DONE.
