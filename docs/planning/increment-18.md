# Increment 18 — S-05.02.01 Evidence-backed Ask Brain

## Session-open audit

Target branch: `increment-10-ai-provider-gateway`.

No new branch is created. The story is intentionally staged on the existing delivery branch because the user explicitly asked to continue it and the repository already uses stacked increments when formal Ready is blocked.

Formal Ready is still **not satisfied** because dependency `S-05.01.01` remains `IN_REVIEW` without executable passing verification. On 2026-09-10 the project owner explicitly deferred running that story's pytest verification locally and on Render until later.

`OQ-005` is no longer a blocker. It was resolved on 2026-09-10 to OpenAI API with `gpt-5.6-terra` as the first production candidate, conditional on the same real quality, security, latency and exact-cost gates defined here.

This increment may therefore stage production code/tests/docs and deployment tooling, but it may end only in `BLOCKED` or `IN_REVIEW`, never `DONE`, until the deferred dependency verification and external acceptance gates actually run.

## Sprint goal

A user can submit a company question to one governed provider/model and receive either:

- an answer whose every server-accepted claim cites currently authorised retrieved evidence, or
- an explicit no-answer when evidence is missing/insufficient.

No ungrounded provider text may reach the user.

## Vertical slice

Question API -> permission-aware retrieval -> bounded evidence context -> governed AI gateway -> strict structured grounding validation -> cited response/no-answer.

This is one user-visible path, not separate retrieval/model/API layers.

## Ready refinement

### Given / When / Then

1. **Authorised grounded answer**  
   Given an authenticated member with `ai.use`, an enabled tenant provider/model, and matching authorised evidence, when Ask Brain is called, then only evidence returned by permission-aware search is sent to the provider and every returned claim resolves to one or more of those evidence IDs.

2. **No evidence**  
   Given no authorised evidence matches the question, when Ask Brain is called, then Brain returns `insufficient_evidence` and performs no provider/secret load.

3. **Invalid grounding**  
   Given provider output contains a missing, empty or unknown citation, when Brain validates the output, then the request fails closed and raw provider text is not returned.

4. **Revocation/tenant isolation**  
   Given evidence belongs to another tenant or an integration is revoked, when Ask Brain retrieves context, then that evidence is absent from the provider prompt and response citations.

5. **Model uncertainty**  
   Given retrieved evidence does not support a useful answer, when the provider returns the no-answer contract, then Brain returns explicit uncertainty with no fabricated citation.

6. **Bounded cost/output**  
   Given a caller or model configuration permits an excessive generation size, when Ask Brain validates the request, then its endpoint-specific output ceiling remains at 8,192 tokens and the generic gateway ceiling cannot widen this read-only answer path.

7. **Exact cache-aware provider cost**  
   Given Terra returns ordinary/cached/output token usage, when Brain materialises request cost, then ordinary and cached input tokens are priced by their separate effective rates and the request-scoped ledger can be independently recomputed. If a required billing dimension is missing or invalid, cost is `unknown` rather than guessed.

8. **Production retrieval/security evaluation**  
   Given the selected production provider/model and a representative human-labelled retrieval dataset, when Phase 1 runs, then retrieval recall is >=90%, forbidden evidence exposure is zero, grounding-contract failures are zero, and automatic source relevance is not mislabelled as semantic citation correctness.

9. **Production semantic citation evaluation**  
   Given the exact Phase 1 generated claims and citations, when a human reviews every claim-citation pair and the bound review is scored, then semantic citation correctness is >=98% before any production citation-quality claim.

## Tasks

- `T-05.02.01.a` Reuse permission-aware retrieval and bind RAG context. **STAGED**
- `T-05.02.01.b` Reuse governed AI gateway with explicit provider/model IDs. **STAGED**
- `T-05.02.01.c` Enforce structured claims/citation validation and fail-closed no-answer behaviour. **STAGED**
- `T-05.02.01.d` Expose authenticated Ask Brain API and safe error mapping. **STAGED**
- `T-05.02.01.e` Add tenant/revocation/grounding/validation/output-bound tests. **STAGED**
- `T-05.02.01.f` Return bounded citation excerpts from the same authorised model context. **STAGED**
- `T-05.02.01.g` Add two-phase deployed evaluation with human semantic claim-citation review. **STAGED**
- `T-05.02.01.h` Protect local labelled/review artifacts from accidental Git commits. **STAGED**
- `T-05.02.01.i` Add safe organisation/runtime discovery for normal `ai.use` users. **STAGED**
- `T-05.02.01.j` Add cache-aware token/cost accounting, request-scoped cost audit and regression tests. **STAGED, NOT EXECUTED**
- `T-05.02.01.k` Add reproducible Render staging Blueprint, managed-Postgres URL handling and deployment runbook. **STAGED, NOT DEPLOYED**
- `T-05.02.01.l` Configure OpenAI/Terra/rate card and run real compatibility + exact-cost smoke. **BLOCKED ON REAL STAGING/CREDENTIALS**
- `T-05.02.01.m` Run real-provider labelled Phase 1 evaluation and human Phase 2 review. **BLOCKED ON REAL STAGING/DATA**
- `T-05.02.01.n` Run end-to-end latency/cost benchmark. **BLOCKED ON REAL STAGING**
- `T-05.02.01.o` Install official WorkOS AuthKit, regenerate the trusted lockfile, build the production frontend/BFF and run browser UAT. **BLOCKED ON PACKAGE-INSTALL/REAL AUTH ENVIRONMENT**
- `T-05.02.01.p` Execute S-05.01.01 pytest verification locally and on Render. **DEFERRED BY PROJECT OWNER**
- `T-05.02.01.q` Sync board, traceability, UAT, changelog and PR without fabricating evidence. **STAGED**

## AI approach decision

Use **RAG**, not fine-tuning or an autonomous agent.

Why: the problem is answering over changing private company evidence with strict per-user permissions. Retrieval can enforce current authorization before any model sees content. Fine-tuning would make deletion/ACL enforcement difficult and is not justified by evidence. An agent adds tool/action risk with no need for this read-only question-answer path. Pure rules/search remain the baseline and are used for the retrieval/no-answer path.

## Provider/model decision

`OQ-005` is resolved:

- provider: OpenAI API;
- first production candidate: `gpt-5.6-terra`;
- no silent fallback;
- Terra becomes Brain's accepted default only after real retrieval, citation, security, latency, compatibility and exact-cost gates pass;
- if Terra misses the quality gate, evaluate the next approved candidate against the identical labelled dataset rather than weakening the gate.

The feature remains provider-neutral at the gateway boundary. The decision selects an evaluated runtime; it does not make Ask Brain code OpenAI-specific.

## Data assessment

Source data is raw/canonical Slack/GitHub/company evidence projected into `SearchDocument`, with provenance and live authorization metadata.

Known limitations:

- current source coverage is incomplete until meeting/document ingestion is built;
- identity/provenance quality depends on source data;
- synthetic retrieval tests do not replace representative customer-labelled retrieval UAT;
- case-level relevant evidence does not prove that a citation semantically supports one generated claim, which is why Phase 2 human claim-citation review is mandatory;
- the production frontend still requires the official WorkOS browser-session-to-FastAPI access-token path and a successful real build.

No training dataset or fine-tuning labels are introduced in this slice. Production evaluation labels are UAT evidence, not model-training data.

## Security, privacy and cost controls

- live tenant/source authorization executes before evidence content is selected;
- no authorised evidence means no provider credential load or model call;
- source evidence is explicitly treated as untrusted prompt data;
- model output is accepted only through strict server-side structured grounding validation;
- citation excerpts are capped at 800 characters and come from already-authorised bounded context;
- Ask Brain generation is capped at 8,192 output tokens;
- prompts/completions remain out of the durable AI request ledger;
- customer-labelled datasets are kept under gitignored `.local/`;
- automatic reports, sensitive review packets and review decisions are kept under gitignored `.evaluation/`;
- provider credentials stay behind the existing secret-store boundary;
- Terra normal input, cached input and output token usage are accounted separately;
- distinct cached pricing fails closed to unknown cost if the provider omits cached-token usage;
- the compatibility smoke validates one exact request ID and independently recomputes its recorded cost, avoiding aggregate-race inference.

Ask Brain's bounded context is below Terra's very-long-context pricing tier. A future generic AI path that can cross a provider pricing tier must add that billing dimension before calling its cost exact.

## Staging path

`render.yaml` now provides a reproducible staging candidate with the API and Render Postgres in the same region. `backend/app/database.py` normalises provider-standard Postgres URLs to the installed Psycopg 3 driver. The staging start path applies Alembic migrations before Uvicorn and uses `/health/ready` to verify the database dependency.

`docs/RENDER_STAGING.md` records the required WorkOS/AWS/CORS inputs and acceptance evidence. `scripts/configure-ask-brain-openai.py` then configures/reuses the approved OpenAI/Terra runtime and exact cache-aware rate card and performs the real request-scoped compatibility/cost smoke.

The Blueprint being checked in is not a deployed environment and is not a production-topology decision under OQ-007.

## Frontend boundary

The current frontend remains a preview. Production acceptance requires the official WorkOS AuthKit integration, a server-side session/access-token path, a BFF/route handler that forwards the bearer token to FastAPI, organisation/runtime discovery, Ask Brain states/citations, and a real build.

The current controlled environment cannot install the WorkOS package or regenerate a trustworthy npm lockfile. Do not fabricate lockfile integrity entries, hand-roll OAuth/PKCE/session security, or substitute a hardcoded browser bearer token. This is an external execution/package-install blocker, not a reason to weaken authentication.

## Change control

The 8,192-token generation ceiling is an endpoint abuse/cost safety bound. OQ-005 now provides the evaluated first runtime candidate, while API/provider selection remains explicit and tenant-scoped.

Schema change `20260910_0016` adds cached-input token usage to the AI request ledger and an optional cached-input token rate to model rate cards. Answers themselves remain transient. Rollback of Ask Brain does not rewrite raw/canonical/search evidence; the migration has a defined downgrade for the new accounting columns.

## Current verification state

The implementation, tests, deployment files and runbooks are staged on `increment-10-ai-provider-gateway`. No new local pytest/Render execution has been performed in this pass because the project owner explicitly said to defer S-05.01.01 execution verification.

The cache-aware cost tests, request-scoped cost route tests and managed-Postgres URL tests are written but not claimed as passing until executed under the repository test gate.

Real OpenAI compatibility/cost smoke, Phase 1 labelled retrieval/RAG evaluation, Phase 2 human semantic citation review, staging p95 benchmark, production frontend build and manual browser UAT have not run because they require the real staging/auth/provider/data environment.

## Definition-of-Done gate

Do not move to DONE until:

- the project owner runs the deferred S-05.01.01 local/Render verification and records passing evidence;
- named Ask Brain/gateway/cost tests execute successfully under the repository test command;
- Ruff and the delivery verifier execute successfully;
- Terra compatibility smoke validates a real request and exact cache-aware cost;
- Phase 1 real-provider evaluation records retrieval recall >=90% with zero forbidden evidence/grounding-contract failures;
- Phase 2 reviews every exact generated claim-citation pair and records semantic citation correctness >=98%;
- staging end-to-end p95 is <10 seconds with error/cost observations recorded;
- official WorkOS frontend integration builds successfully;
- authenticated frontend/manual UAT passes;
- final acceptance evidence is recorded without storing customer secrets/content in repository artifacts.
