# Ask Brain staging acceptance runbook

Story: `S-05.02.01`. This runbook exists to turn the remaining external acceptance work into one reproducible sequence. Its presence is not evidence that staging, evaluation, performance or UAT has passed.

## Approved first runtime

OQ-005 was resolved on 2026-09-10:

- provider: OpenAI API;
- first model candidate: `gpt-5.6-terra`;
- Brain provider adapter: `openai_chat_completions`;
- API URL: `https://api.openai.com/v1/chat/completions`;
- Ask Brain application output ceiling: 8,192 tokens;
- reviewed Terra price: USD 2 per million input tokens and USD 12 per million output tokens, represented by Brain as 2,000 and 12,000 nano-USD/token respectively.

Terra becomes the default only after the same deployment/model passes the real quality, security, latency and cost gates. No silent fallback is allowed.

The current OpenAI Chat Completions API documents `max_completion_tokens` as the preferred completion ceiling and `max_tokens` as deprecated. Brain's provider-neutral OpenAI-compatible adapter currently uses its existing completion-limit field. Therefore the bootstrap below performs a real provider smoke and must pass before the runtime is accepted. Do not edit the generic adapter merely to make the configuration look compatible without observing a failure.

## Data-policy precondition

Before sending customer evidence:

1. API input/output data sharing is disabled.
2. Confirm the customer's permitted OpenAI retention mode.
3. Use `BRAIN_OPENAI_RETENTION_MODE=standard` only when the customer's contract/policy permits the normal API retention terms.
4. Use `BRAIN_OPENAI_RETENTION_MODE=zdr` only after eligible Zero Data Retention is actually enabled for the relevant OpenAI organisation/project.
5. Never treat the local environment variable as proof that OpenAI settings are configured. It is an operator attestation recorded for the run.
6. Provider credentials are submitted only to Brain's admin API and are stored by the configured secret-store backend; do not put the API key in repository files or command-line arguments.

## Staging prerequisites

Required before bootstrap:

- deployed Brain API candidate at an HTTPS URL;
- PostgreSQL/migrations operational;
- AWS Secrets Manager backend operational for provider credentials;
- `api.openai.com` present in `BRAIN_AI_PROVIDER_ALLOWED_HOSTS` for the deployed backend;
- a WorkOS access token for a Brain Owner/Admin in the isolated staging organisation;
- a paid OpenAI API project key with the approved data settings;
- representative non-sensitive evidence in the staging organisation for initial smoke/performance;
- a separately prepared human-labelled evaluation dataset for the production quality gate.

## 1. Configure provider, model, rate card and run compatibility smoke

Do not export secrets in a shared shell history or committed `.env` file. In a controlled shell:

```bash
export BRAIN_ADMIN_TOKEN='<owner-or-admin-workos-access-token>'
export OPENAI_API_KEY='<openai-api-key>'
export BRAIN_OPENAI_RETENTION_MODE='standard' # or zdr, after real policy verification

python scripts/configure-ask-brain-openai.py \
  --base-url 'https://<brain-staging-host>' \
  --organization-id '<brain-org-uuid>' \
  --confirm-customer-policy
```

The script is deliberately fail-closed. It:

- reuses an existing OpenAI provider only when provider key, adapter and approved URL agree;
- refuses revoked/non-reenableable provider state;
- creates/enables `gpt-5.6-terra` without silently changing an existing model ceiling;
- creates the reviewed Terra rate card only if doing so cannot overlap current/future pricing;
- refuses mismatched existing pricing rather than rewriting historical cost policy;
- executes a real governed `/ai/invoke` call;
- verifies the call appears in Brain's usage ledger with exact, not unknown, cost;
- prints IDs, token counts, latency and nano-USD cost only; it never prints either bearer/API secret.

A failed compatibility smoke is a blocker. If OpenAI rejects the current generic Chat Completions adapter, capture the provider-safe error/request ID and implement a dedicated modern adapter before retrying. Do not weaken the gateway or disable the smoke.

## 2. Prepare the real retrieval/RAG evaluation set

Use `ops/evals/ask-brain.dataset.example.json` only as schema guidance. It is intentionally not eligible for a production PASS.

Create a private local dataset under `.local/` using real representative staging evidence. For each case, a human reviewer must establish the supporting canonical event IDs and any forbidden event IDs. Set the production/retrieval-review flags to true only after that review actually happened.

`.local/` and `.evaluation/` are gitignored. Do not paste customer evidence into BOARD, TRACEABILITY, CHANGELOG, GitHub Actions inputs or committed test fixtures.

## 3. Run automatic deployed RAG evaluation

Use the same provider/model IDs emitted by the bootstrap:

```bash
export BRAIN_EVAL_TOKEN='<real-evaluation-user-workos-token>'

python scripts/run-ask-brain-evaluation.py \
  --base-url 'https://<brain-staging-host>' \
  --organization-id '<brain-org-uuid>' \
  --provider-id '<provider-uuid>' \
  --model-id '<terra-model-uuid>' \
  --dataset '.local/ask-brain.production-eval.json' \
  --output '.evaluation/ask-brain-report.json' \
  --review-packet '.evaluation/ask-brain-review-packet.json' \
  --review-template '.evaluation/ask-brain-review.json'
```

Automatic production gate requirements include:

- retrieval recall >=90%;
- zero forbidden evidence exposures;
- zero grounding-contract failures;
- no unsafe answer on a labelled no-answer case.

The automatic phase does **not** claim semantic citation correctness.

## 4. Human semantic citation review

A human reviewer opens the sensitive review packet and judges whether every exact generated claim is actually supported by each cited excerpt/event. Complete every `supported` field in the generated review template, plus reviewer and reviewed-at metadata.

Then run:

```bash
python scripts/score-ask-brain-review.py \
  --automatic-report '.evaluation/ask-brain-report.json' \
  --review '.evaluation/ask-brain-review.json' \
  --output '.evaluation/ask-brain-final-score.json'
```

Production quality gate:

- semantic claim/citation correctness >=98%;
- the automatic gate also passed;
- the scorer reports `production_passed=true`.

If Terra misses the citation gate, keep it non-default and repeat the identical dataset with `gpt-5.6-sol`. Do not change the labelled set to make a model pass.

## 5. Run end-to-end latency and exact-cost benchmark

The checked-in `ask_brain_end_to_end` scenario measures the real `/ask-brain` route, not a raw provider call. A request counts as successful only when HTTP is successful, the response status is `answer`, and `ai_request_id` is non-null. This prevents a fast no-evidence response from faking a good RAG benchmark.

Required environment when running the benchmark script directly:

```bash
export BRAIN_PERF_BEARER_TOKEN='<real-benchmark-user-token>'
export BRAIN_PERF_ORGANIZATION_ID='<brain-org-uuid>'
export BRAIN_PERF_SEARCH_QUERY='<representative-non-sensitive-search>'
export BRAIN_PERF_ENABLE_AI='true'
export BRAIN_PERF_ENABLE_ASK_BRAIN='true'
export BRAIN_PERF_PROVIDER_ID='<provider-uuid>'
export BRAIN_PERF_MODEL_ID='<terra-model-uuid>'
export BRAIN_PERF_AI_PROMPT='Return exactly this word: acknowledged'
export BRAIN_PERF_ASK_BRAIN_QUESTION='<question-with-known-authorised-answer>'

python scripts/run-performance-benchmark.py \
  --base-url 'https://<brain-staging-host>' \
  --config ops/performance/budgets.json \
  --output '.performance/report.json'
```

Ask Brain acceptance requires the checked-in p95 target (<10 seconds), configured minimum success rate, and exact cost completeness to pass. Record the provider/model, p50/p95/p99, error rate, token counts and exact cost per successful question. Do not claim a cost ceiling unless product economics later defines one.

The GitHub `Performance Gate` can run the same workload once GitHub Actions can obtain a runner. At present, ordinary branch workflows have repeatedly failed before step 1, so workflow presence is not evidence.

## 6. Frontend production path

The current UI is a sample preview and cannot be used for feature acceptance.

The production frontend path must use the existing WorkOS authority rather than ChatGPT-host authentication or hardcoded tokens:

1. Install the official WorkOS AuthKit Next.js package and regenerate `package-lock.json` using the repository's normal package manager.
2. Use the Next.js 16 server-side AuthKit flow (`proxy.ts`/callback/sign-in contract as supported by the installed SDK).
3. Keep the WorkOS session/access token server-side.
4. Add a server-side BFF/route handler that obtains the WorkOS access token and forwards it as Bearer to FastAPI.
5. Use `GET /api/v1/organizations` to discover the signed-in user's Brain organisations.
6. Use `GET /api/v1/organizations/{org}/ai/runtime-options` to discover enabled AI runtime IDs for an `ai.use` member without granting `ai.manage`.
7. Render Ask Brain success, loading, empty/no-answer, provider error, auth error and citation/excerpt states.
8. Never serialize provider credentials, the WorkOS access token or unrestricted source evidence into client configuration.

The current isolated execution environment cannot reach npm to install AuthKit or generate a trustworthy lockfile. Do **not** manually fabricate npm integrity/transitive lock entries. Frontend implementation is therefore externally blocked until the dependency can be installed and the actual vinext/Next build can run.

## 7. Manual frontend/UAT acceptance

After the real authenticated frontend is deployed, execute `UAT/F-05.02.md` with at least:

- grounded answer and independently verifiable citation;
- no-answer when evidence is missing;
- two users with different restricted-source access;
- integration revocation;
- controlled prompt-injection evidence;
- loading/empty/error/success UI states;
- keyboard/focus/accessibility checks for the Ask Brain interaction.

Record tester, date, deployed commit and defects/fixes. Only after those checks pass may the feature be called PASSED.

## 8. DONE/PASSED/merge gate

Do not mark S-05.01.01 or S-05.02.01 engineering-DONE until the repository's named Ruff/Pytest/verifier/CI requirements have actually executed and passed. Do not call F-05.02 PASSED until the real-data backend and manual frontend UAT is recorded.

Merge only after:

1. S-05.01.01 has executable passing evidence;
2. Ask Brain engineering tests/verifier/CI pass;
3. Terra compatibility smoke + exact cost pass;
4. real retrieval/RAG quality gates pass;
5. deployed Ask Brain performance passes;
6. authenticated frontend is built/tested;
7. manual real-data UAT passes;
8. BOARD/TRACEABILITY/UAT contain the corresponding non-fabricated evidence.
