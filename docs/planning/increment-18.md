# Increment 18 — S-05.02.01 Evidence-backed Ask Brain

## Session-open audit

Target branch: `increment-10-ai-provider-gateway`.

No new branch is created. The story is intentionally staged on the existing delivery branch because the user explicitly asked to start it and the repository already uses stacked increments when formal Ready is blocked.

Formal Ready is **not satisfied**:

- dependency `S-05.01.01` is still `IN_REVIEW` without executable passing verification;
- `OQ-005` still blocks the production provider/model policy and the real-model evaluation baseline.

This increment therefore stages production code/tests/docs but may end only in `BLOCKED` or `IN_REVIEW`, never `DONE`, until those conditions are resolved.

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
   Given an authenticated member with `ai.use`, an enabled tenant provider/model, and matching authorised evidence, when Ask Brain is called, then only evidence returned by the permission-aware search is sent to the provider and every returned claim resolves to one or more of those evidence IDs.

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

7. **Production retrieval/security evaluation**  
   Given the selected production provider/model and a representative human-labelled retrieval dataset, when Phase 1 runs, then retrieval recall is >=90%, forbidden evidence exposure is zero, grounding-contract failures are zero, and automatic source relevance is not mislabelled as semantic citation correctness.

8. **Production semantic citation evaluation**  
   Given the exact Phase 1 generated claims and citations, when a human reviews every claim-citation pair and the bound review is scored, then semantic citation correctness is >=98% before any production citation-quality claim.

## Tasks

- `T-05.02.01.a` Reuse permission-aware retrieval and bound RAG context. **STAGED**
- `T-05.02.01.b` Reuse governed AI gateway with explicit provider/model IDs; no default model. **STAGED**
- `T-05.02.01.c` Enforce structured claims/citation validation and fail-closed no-answer behaviour. **STAGED**
- `T-05.02.01.d` Expose authenticated Ask Brain API and safe error mapping. **STAGED**
- `T-05.02.01.e` Add tenant/revocation/grounding/validation/output-bound tests. **STAGED**
- `T-05.02.01.f` Return bounded citation excerpts from the same authorised model context. **STAGED**
- `T-05.02.01.g` Add two-phase deployed evaluation with human semantic claim-citation review. **STAGED**
- `T-05.02.01.h` Protect local labelled/review artifacts from accidental Git commits. **STAGED**
- `T-05.02.01.i` Add operator docs, UAT, board and traceability. **STAGED**
- `T-05.02.01.j` Run executable Ruff/Pytest/verifier once a runner can start. **BLOCKED EXTERNALLY**
- `T-05.02.01.k` Run real-provider labelled eval + latency/cost UAT after `OQ-005`. **PENDING**
- `T-05.02.01.l` Run authenticated frontend/manual UAT after the production WorkOS browser-token path exists. **PENDING**

## AI approach decision

Use **RAG**, not fine-tuning or an autonomous agent.

Why: the problem is answering over changing private company evidence with strict per-user permissions. Retrieval can enforce current authorization before any model sees content. Fine-tuning would make deletion/ACL enforcement difficult and is not justified by evidence. An agent adds tool/action risk with no need for this read-only question-answer path. Pure rules/search remain the baseline and are used for the retrieval/no-answer path.

## Data assessment

Source data is raw/canonical Slack/GitHub/company evidence projected into `SearchDocument`, with provenance and live authorization metadata.

Known limitations:

- current source coverage is incomplete until meeting/document ingestion is built;
- identity/provenance quality depends on source data;
- OQ-005 still controls the real production provider/model/data-policy baseline;
- synthetic retrieval tests do not replace representative customer-labelled retrieval UAT;
- case-level relevant evidence does not prove that a citation semantically supports one generated claim, which is why Phase 2 human claim-citation review is mandatory;
- the current frontend is a preview and does not yet expose a production WorkOS browser-session-to-FastAPI token path.

No training dataset or fine-tuning labels are introduced in this slice. Production evaluation labels are UAT evidence, not model-training data.

## Security and privacy controls

- live tenant/source authorization executes before evidence content is selected;
- no authorised evidence means no provider credential load or model call;
- source evidence is explicitly treated as untrusted prompt data;
- model output is accepted only through strict server-side structured grounding validation;
- citation excerpts are capped at 800 characters and come from already-authorised bounded context;
- Ask Brain generation is capped at 8,192 output tokens;
- prompts/completions remain out of the durable AI request ledger;
- customer-labelled datasets are kept under gitignored `.local/`;
- automatic reports, sensitive review packets and review decisions are kept under gitignored `.evaluation/`;
- the sensitive review packet is required only because a human cannot truthfully judge semantic support without seeing the exact generated claim and source excerpt; local files are written owner-readable only where the operating system supports those permissions.

## Change control

No business rule is invented for the default provider/model. Provider/model selection remains `OQ-005`. The API therefore requires explicit configured IDs.

The 8,192-token generation ceiling is an endpoint abuse/cost safety bound, not a provider-selection rule.

No schema change is needed. Answers stay transient; governed AI request metadata already exists. Rollback is code-only and does not rewrite raw/canonical/search evidence or AI request history.

## Current verification state

Implementation is staged through commit `f4ff8217ac02b6392cede6e709ccdbcab124b33f` on the existing branch. Backend CI run 34405201146 failed before any workflow step and exposes no executed test steps. Therefore Ruff/Pytest are **not** claimed as passed.

The available local runtime has Python/FastAPI/SQLAlchemy/Pydantic/Pytest, but it does not have Ruff and outbound package installation is unavailable. That local environment is not equivalent to the repository CI gate and is not used as substitute evidence.

## Definition-of-Done gate

Do not move to DONE until:

- named tests execute successfully under the repository test command;
- Ruff executes successfully under the repository lint command;
- the delivery verifier passes;
- `S-05.01.01` dependency is engineering-DONE;
- OQ-005 is resolved for the production provider/model/data policy;
- Phase 1 real-provider evaluation records retrieval recall >=90% with zero forbidden evidence/grounding-contract failures;
- Phase 2 reviews every exact generated claim-citation pair and records semantic citation correctness >=98%;
- staging p95 latency/cost result is recorded;
- authenticated frontend/manual UAT passes;
- final acceptance evidence is recorded without storing customer secrets/content in repository artifacts.
