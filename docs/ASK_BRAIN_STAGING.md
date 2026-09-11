# Ask Brain staging acceptance runbook

Story: `S-05.02.01`. This runbook turns the remaining external acceptance work into one reproducible sequence. Its presence is not evidence that staging, evaluation, performance or UAT passed.

## Approved first runtime

OQ-005 was resolved on 2026-09-10:

- provider: OpenAI API;
- first model candidate: `gpt-5.6-terra`;
- Brain provider adapter: `openai_chat_completions`;
- API URL: `https://api.openai.com/v1/chat/completions`;
- Ask Brain application output ceiling: 8,192 tokens;
- reviewed Brain rate-card representation: ordinary input, cached input and output are priced separately.

Terra becomes the default only after the same deployment/model passes the real quality, security, latency and exact-cost gates. No silent fallback is allowed. Revalidate the provider's official current pricing/protocol before a production cost acceptance run; do not assume a historical reviewed rate card is still current merely because it is checked into Brain.

Brain records total input tokens and cached input tokens separately. If a rate card has a distinct cached-input price but the provider does not report the cached-input usage dimension, Brain records request cost as `unknown` rather than assuming zero cached tokens. Invalid billing dimensions also fail closed.

## Data-policy precondition

Before sending customer evidence:

1. API input/output data sharing is disabled unless the customer's approved policy explicitly says otherwise.
2. Confirm the customer's permitted provider retention mode.
3. Use `BRAIN_OPENAI_RETENTION_MODE=standard` only when the customer's contract/policy permits the normal API retention terms.
4. Use `BRAIN_OPENAI_RETENTION_MODE=zdr` only after eligible Zero Data Retention is actually enabled for the relevant provider organisation/project.
5. Never treat a local environment variable as proof that the external provider setting is configured; it is an operator attestation for the run.
6. Provider credentials are submitted only to Brain's governed admin API and stored by the configured secret-store backend; never commit them or pass them through browser configuration.

## Staging prerequisites

The current Render acceptance path is defined in `render.yaml` and `docs/RENDER_STAGING.md`. Before Ask Brain's real provider gate begins:

- the ordered backend acceptance chain has executed successfully on the exact staging commit through the Ask Brain stage;
- PostgreSQL/migrations/pgvector are operational;
- S-05.01 realistic permission/revocation/recall/latency UAT has passed and is recorded;
- S-02.04 real file/transcript lifecycle UAT has passed and is recorded;
- AWS Secrets Manager is operational for provider credentials;
- Render uses least-privilege AWS credentials for the Brain secret prefix;
- `api.openai.com` is present in `BRAIN_AI_PROVIDER_ALLOWED_HOSTS`;
- `BRAIN_CORS_ORIGINS` is the exact frontend origin, never `*`;
- `BRAIN_WORKOS_CLIENT_ID` matches the WorkOS application used by the frontend;
- standard AuthKit tokens are accepted through `client_id` validation; leave `BRAIN_WORKOS_AUDIENCE` unset unless an explicit custom `aud` claim is intentionally required;
- the WorkOS JWT Template provides `urn:brain:user_email` as documented in `docs/WORKOS_FRONTEND_ACCEPTANCE.md`;
- a real WorkOS access token exists for the staging Brain Owner/Admin running the bootstrap;
- a paid OpenAI API project key has the approved data settings;
- representative non-sensitive evidence exists in staging;
- a separately prepared human-labelled evaluation dataset exists for the production quality gate.

Render Free is staging only. Cold starts and temporary/free database characteristics must not be treated as production architecture or mixed blindly into warmed steady-state performance measurements.

## 1. Configure provider, model, rate card and run compatibility smoke

Do not export secrets in shared shell history or commit them in `.env`. In a controlled environment:

```bash
export BRAIN_ADMIN_TOKEN='<owner-or-admin-workos-access-token>'
export OPENAI_API_KEY='<openai-api-key>'
export BRAIN_OPENAI_RETENTION_MODE='standard' # or zdr after real policy verification

python scripts/configure-ask-brain-openai.py \
  --base-url 'https://<brain-staging-host>' \
  --organization-id '<brain-org-uuid>' \
  --confirm-customer-policy
```

The script must fail closed. It should:

- reuse an existing OpenAI provider only when provider key, adapter and approved URL agree;
- refuse revoked/non-reenableable provider state;
- create/enable the accepted model candidate without silently changing an incompatible existing ceiling;
- create/reuse only a reviewed non-overlapping rate card;
- refuse mismatched pricing instead of rewriting historical cost policy;
- execute a real governed `/ai/invoke` call;
- read the exact request's cost record;
- require the billing dimensions needed by the active rate card;
- independently recompute exact nano-USD cost;
- print only non-secret IDs, usage, latency and cost.

A failed provider compatibility or exact-cost smoke blocks Ask Brain acceptance. Do not weaken gateway validation simply to make the provider call succeed.

## 2. Prepare the real retrieval/RAG evaluation set

Use `ops/evals/ask-brain.dataset.example.json` only as schema guidance; it is not production evidence.

Create a private dataset under `.local/` using representative authorised staging evidence. For each case a human must establish expected supporting canonical event IDs and forbidden event IDs. Keep real customer evidence under the ignored local/evaluation paths, not BOARD/TRACEABILITY/CHANGELOG or committed fixtures.

## 3. Run automatic deployed RAG evaluation

Use the exact provider/model IDs accepted by the compatibility smoke:

```bash
export BRAIN_EVAL_TOKEN='<real-evaluation-user-workos-token>'

python scripts/run-ask-brain-evaluation.py \
  --base-url 'https://<brain-staging-host>' \
  --organization-id '<brain-org-uuid>' \
  --provider-id '<provider-uuid>' \
  --model-id '<model-uuid>' \
  --dataset '.local/ask-brain.production-eval.json' \
  --output '.evaluation/ask-brain-report.json' \
  --review-packet '.evaluation/ask-brain-review-packet.json' \
  --review-template '.evaluation/ask-brain-review.json'
```

Automatic production gate requirements:

- retrieval recall >=90%;
- zero forbidden evidence exposure;
- zero grounding-contract failures;
- no unsafe answer on a labelled no-answer case.

This automatic phase does **not** claim semantic citation correctness.

## 4. Human semantic citation review

A human reviewer must judge every exact generated claim against every cited excerpt/event from the same evaluation run. Complete every review field plus reviewer/date metadata, then run:

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

If the first model candidate misses the quality gate, keep it non-default and evaluate the next approved candidate on the **same labelled set**. Do not alter labels merely to make a model pass.

## 5. Run end-to-end latency and exact-cost benchmark

The `ask_brain_end_to_end` scenario measures the real `/ask-brain` route. A request counts as successful only when HTTP succeeds, response status is `answer`, and `ai_request_id` is non-null; a fast no-evidence response must not fake a good RAG benchmark.

Example direct run:

```bash
export BRAIN_PERF_BEARER_TOKEN='<real-benchmark-user-token>'
export BRAIN_PERF_ORGANIZATION_ID='<brain-org-uuid>'
export BRAIN_PERF_SEARCH_QUERY='<representative-non-sensitive-search>'
export BRAIN_PERF_ENABLE_AI='true'
export BRAIN_PERF_ENABLE_ASK_BRAIN='true'
export BRAIN_PERF_PROVIDER_ID='<provider-uuid>'
export BRAIN_PERF_MODEL_ID='<model-uuid>'
export BRAIN_PERF_AI_PROMPT='Return exactly this word: acknowledged'
export BRAIN_PERF_ASK_BRAIN_QUESTION='<question-with-known-authorised-answer>'

python scripts/run-performance-benchmark.py \
  --base-url 'https://<brain-staging-host>' \
  --config ops/performance/budgets.json \
  --output '.performance/report.json'
```

Ask Brain acceptance requires the checked-in p95 target (<10 seconds), configured minimum success rate and exact-cost completeness. Record provider/model, p50/p95/p99, error rate, total/cached/output tokens and exact cost per successful question. Do not invent an economic cost ceiling if product economics has not approved one.

## 6. Official WorkOS / frontend path

The current root UI is still an explicit sample preview. Production acceptance must use the official AuthKit path in `docs/WORKOS_FRONTEND_ACCEPTANCE.md`.

The repository currently stages the provider-independent frontend pieces:

- `app/brain-api.ts` — server-side typed Brain API client with HTTPS/no-store/Bearer constraints;
- `app/brain-bff.ts` — strict Ask Brain BFF input contract;
- `app/production-executive-workspace.tsx` — live organisation/executive composition;
- `app/live-workspace.tsx` — Project Command Centre + Executive Overview renderer;
- `app/ask-brain-panel.tsx` — citation-first browser interaction that expects only a same-origin authenticated BFF endpoint.

The missing activation step is intentionally blocked until the official npm packages can be installed and a trustworthy lockfile generated. This repo uses Next.js 15, so the official AuthKit integration must use the documented **Next.js <=15 `middleware.ts`** path, not a Next.js 16 `proxy.ts` path.

After registry access is available:

1. run `npm install @workos-inc/authkit-nextjs @workos-inc/node` normally so npm generates the lockfile;
2. configure `WORKOS_CLIENT_ID`, `WORKOS_API_KEY`, `WORKOS_COOKIE_PASSWORD` and `NEXT_PUBLIC_WORKOS_REDIRECT_URI` outside Git;
3. configure the WorkOS JWT Template `{ "urn:brain:user_email": {{ user.email }} }`;
4. add the official AuthKit middleware/callback/provider/sign-in/session integration;
5. use `withAuth()` server-side to obtain the access token;
6. call FastAPI through `app/brain-api.ts` or a same-origin server BFF;
7. never serialize WorkOS access/refresh tokens, API keys, encrypted session internals or provider credentials to the browser.

Do **not** fabricate npm integrity/transitive lock entries and do not hand-roll OAuth/PKCE/session security while registry access is unavailable.

## 7. Manual frontend/UAT acceptance

After the real authenticated frontend is deployed, execute at least:

- grounded Ask Brain answer and independently verifiable citations;
- no-answer when authorised evidence is insufficient;
- two users with different restricted-source/project access;
- cross-organisation negative access;
- integration/resource revocation;
- controlled prompt-injection evidence;
- Project Command Centre deterministic progress/evidence states;
- Executive Overview cost completeness, budget warnings and API `not_modeled` cost state;
- loading, empty, permission-denied, provider-error and success states;
- keyboard/focus/screen-reader/accessibility checks;
- confirmation that no employee productivity/worth/performance score exists.

Record tester, date, exact deployed frontend/backend commits and defect/retest references.

## 8. DONE/PASSED/merge gate

Acceptance has now begun; the old 2026-09-10 deferment is no longer the current instruction. Nevertheless, no story can be promoted merely because the harness exists.

Do not mark S-05.02.01 engineering-DONE until:

1. the ordered backend chain has real passing evidence through the Ask Brain stage on the accepted commit;
2. S-05.01 and S-02.04 have their own realistic UAT evidence;
3. provider compatibility + exact cost pass;
4. real automatic retrieval/RAG quality gates pass;
5. human citation review passes >=98%;
6. deployed Ask Brain performance passes;
7. official WorkOS frontend packages are installed with a real generated lockfile and the frontend builds;
8. authenticated manual/browser/accessibility UAT passes.

Keep PR #13 draft and unmerged until the required acceptance evidence for the release scope exists and BOARD/TRACEABILITY/UAT are updated without fabricated PASS results.
