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

6. **Production evaluation**  
   Given the selected production provider/model and a representative labelled evaluation set, when the Ask Brain evaluation runs, then citation correctness is >=98%, retrieval recall is >=90%, and measured latency/cost are recorded before DONE.

## Tasks

- `T-05.02.01.a` Reuse permission-aware retrieval and bound RAG context.
- `T-05.02.01.b` Reuse governed AI gateway with explicit provider/model IDs; no default model.
- `T-05.02.01.c` Enforce structured claims/citation validation and fail-closed no-answer behaviour.
- `T-05.02.01.d` Expose authenticated Ask Brain API and safe error mapping.
- `T-05.02.01.e` Add grounding/security/authorization tests.
- `T-05.02.01.f` Add operator docs, UAT and traceability.
- `T-05.02.01.g` Run real-provider labelled eval + latency/cost UAT after `OQ-005` and executable runner are available.

## AI approach decision

Use **RAG**, not fine-tuning or an autonomous agent.

Why: the problem is answering over changing private company evidence with strict per-user permissions. Retrieval can enforce current authorization before any model sees content. Fine-tuning would make deletion/ACL enforcement difficult and is not justified by evidence. An agent adds tool/action risk with no need for this read-only question-answer path. Pure rules/search remain the baseline and are used for the retrieval/no-answer path.

## Data assessment

Source data is raw/canonical Slack/GitHub/company evidence projected into `SearchDocument`, with provenance and live authorization metadata.

Known limitations:

- current source coverage is incomplete until meeting/document ingestion is built;
- identity/provenance quality depends on source data;
- model semantic citation correctness is not yet measured because `OQ-005` is unresolved;
- retrieval recall has a synthetic test but still needs representative customer UAT.

No training dataset or fine-tuning labels are introduced in this slice.

## Change control

No business rule is invented for the default provider/model. Provider/model selection remains `OQ-005`. The API therefore requires explicit configured IDs.

No schema change is needed. Answers stay transient; governed AI request metadata already exists.

## Definition-of-Done gate

Do not move to DONE until:

- named tests execute successfully;
- the delivery verifier passes;
- `S-05.01.01` dependency is engineering-DONE;
- real-provider labelled citation correctness >=98%;
- retrieval recall >=90%;
- staging latency/cost result is recorded;
- manual UAT passes.
