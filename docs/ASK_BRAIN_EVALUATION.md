# Ask Brain production evaluation

This evaluator turns the explicit `S-05.02.01` production gates into a reproducible deployed test. It does not replace human evidence labelling.

## What it measures

For every labelled question the runner calls both permission-aware `/search` and `/ask-brain` as the same real user.

It reports:

- retrieval recall against human-labelled supporting canonical events;
- citation correctness as **claim-citation pairs**, not merely whether a citation field exists;
- answer/no-answer status accuracy;
- forbidden evidence exposure;
- grounding-contract failures such as an answer with no resolvable citation;
- per-question Ask Brain latency without storing question or answer content in the report.

The production pass gate is exactly the product contract already recorded in the backlog:

- retrieval recall >= 90%;
- citation correctness >= 98%;
- zero forbidden evidence exposures;
- zero grounding-contract failures;
- zero answers on cases explicitly labelled `insufficient_evidence`.

The evaluator also requires both dataset flags `production_labelled=true` and `human_reviewed=true`. An example or synthetic dataset can run, but it can never produce a production PASS.

## Label format

Start from `ops/evals/ask-brain.dataset.example.json` and create a separate UAT dataset. Do not overwrite the example with customer evidence.

Each positive case must list the exact `canonical_event_id` values that a human reviewer has confirmed support the answer. Optional `forbidden_canonical_event_ids` are evidence records the test user must never receive; use them for permission-boundary cases.

`production_labelled` means the cases represent the intended production workload rather than synthetic fixtures. `human_reviewed` means a person checked the supporting evidence labels. Set either flag to `true` only when that statement is actually true.

## Run

Keep the bearer token in an environment variable so it does not appear in shell history or the report.

```bash
export BRAIN_EVAL_TOKEN="<real-user-access-token>"
PYTHONPATH=backend python scripts/run-ask-brain-evaluation.py \
  --base-url "https://<brain-api-host>/api/v1" \
  --organization-id "<uuid>" \
  --provider-id "<uuid>" \
  --model-id "<uuid>" \
  --dataset ".local/ask-brain-production-eval.json" \
  --output ".evaluation/ask-brain-report.json"
```

Exit codes:

- `0`: eligible labelled dataset and all production gates passed;
- `2`: eligible dataset ran but one or more gates failed;
- `3`: dataset ran but is not eligible for a production claim;
- `64`: configuration/transport failure prevented a valid evaluation.

## Privacy and evidence handling

The runner necessarily sends each question to the deployed Brain API and configured AI provider through the normal governed path. The local machine-readable report deliberately excludes question text, retrieved content, answer text, bearer tokens and provider credentials. It retains only case IDs, canonical event IDs reduced to counts in the evaluation object, HTTP status, latency, provider/model IDs and aggregate metrics.

Do not commit a customer-labelled dataset or report unless its metadata has been reviewed for customer confidentiality. Store production UAT evidence according to the organisation's approved evidence-retention process.

## What this still does not prove

A passing report is necessary, not sufficient. It does not replace manual inspection of representative answers, source revocation testing, prompt-injection testing, provider/model cost measurement, frontend acceptance or the executable repository CI/Delivery Verifier gate.
