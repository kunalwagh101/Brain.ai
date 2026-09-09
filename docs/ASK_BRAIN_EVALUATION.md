# Ask Brain production evaluation

`S-05.02.01` has two different questions to prove:

1. Did retrieval find the evidence a user was allowed to see without leaking forbidden evidence?
2. Does each generated factual claim actually follow from each citation attached to that claim?

Those are not the same metric. Brain therefore uses a two-phase evaluation rather than pretending case-level relevance proves semantic citation correctness.

## Phase 1 — automatic deployed gate

The automatic runner calls both permission-aware `/search` and `/ask-brain` as the same real user.

It measures:

- retrieval recall against human-labelled supporting canonical events;
- citation-target precision: whether cited canonical events were among the case-level labelled relevant events;
- answer/no-answer status accuracy;
- forbidden evidence exposure;
- grounding-contract failures such as an answer with no resolvable citation;
- per-question Ask Brain latency.

**Citation-target precision is diagnostic only. It is not the product's 98% citation-correctness claim.** A relevant source may still fail to support one specific generated sentence.

The automatic production gate requires:

- retrieval recall >= 90%;
- zero forbidden evidence exposures;
- zero grounding-contract failures;
- zero answers on cases explicitly labelled `insufficient_evidence`.

The dataset must also have `production_labelled=true` and `retrieval_labels_human_reviewed=true`. An example or synthetic dataset cannot clear the automatic production gate.

## Phase 2 — human semantic citation review

The runner creates three local artifacts:

- `.evaluation/ask-brain-report.json`: content-free automatic report;
- `.evaluation/ask-brain-review-packet.json`: **sensitive** packet containing the exact generated claims and bounded citation excerpts from that run;
- `.evaluation/ask-brain-review.json`: content-free review template with one entry for every exact claim-citation pair.

The packet and review template are bound to the exact automatic report with an evaluation run ID and SHA-256. Reviewers inspect each claim against its cited excerpt/source and change each `supported` value in the review template from `null` to `true` or `false`. They also fill `reviewer` and timezone-aware `reviewed_at`.

The scorer refuses incomplete reviews, pair mismatches, a review for a different run, or a modified automatic report.

The final production gate requires:

- the Phase 1 automatic gate passed;
- every observed claim-citation pair was reviewed;
- semantic citation correctness >= 98% (`supported pairs / all observed pairs`);
- at least one claim-citation pair exists in the production evaluation.

Only the final scorer's `production_passed=true` represents the 98% product gate.

## Local data safety

`.local/` and `.evaluation/` are repository-gitignored and regression-tested so labelled customer datasets, review packets and reports are not accidentally committed.

The automatic report and final scored report retain no question, answer or excerpt content. The review packet **does contain customer questions, generated claims and bounded source excerpts** because a human cannot truthfully judge semantic support without seeing them. It is written with owner-only file permissions (`0600`) and should be deleted after the approved UAT evidence has been recorded.

The human review template contains canonical event IDs and review decisions but no source/answer text. Treat it as customer metadata and keep it under the approved evidence-retention policy.

## Label dataset

Start from `ops/evals/ask-brain.dataset.example.json` and create the real dataset under `.local/`.

For each positive case, a human reviewer identifies the canonical events expected to be relevant for retrieval. `forbidden_canonical_event_ids` can be used for permission-boundary cases.

`retrieval_labels_human_reviewed=true` means those source relevance labels were checked by a person. It does **not** mean the later generated claims were semantically reviewed; Phase 2 handles that separately.

## Run Phase 1

```bash
export BRAIN_EVAL_TOKEN="<real-user-access-token>"
PYTHONPATH=backend python scripts/run-ask-brain-evaluation.py \
  --base-url "https://<brain-api-host>/api/v1" \
  --organization-id "<uuid>" \
  --provider-id "<uuid>" \
  --model-id "<uuid>" \
  --dataset ".local/ask-brain-production-eval.json"
```

Exit codes:

- `0`: eligible dataset and automatic gate passed; semantic review still required;
- `2`: eligible dataset ran but automatic gate failed;
- `3`: dataset is not eligible for a production claim;
- `64`: configuration/transport failure prevented a valid run.

## Complete Phase 2

Open the sensitive review packet locally. For every claim-citation pair, verify the cited evidence actually supports the exact generated claim. Fill the corresponding `supported` value in `.evaluation/ask-brain-review.json`.

Then run:

```bash
PYTHONPATH=backend python scripts/score-ask-brain-review.py \
  --report ".evaluation/ask-brain-report.json" \
  --review ".evaluation/ask-brain-review.json"
```

The final scorer exits `0` only when the automatic gate and >=98% human-reviewed semantic citation-correctness gate both pass. Exit `2` means a completed valid review failed a production metric. Exit `64` means the review/report contract is invalid or incomplete.

## What this still does not prove

A passing final report is necessary, not sufficient. It does not replace source-revocation testing, prompt-injection testing, provider/model cost measurement, frontend acceptance or executable repository CI/Delivery Verifier evidence.
