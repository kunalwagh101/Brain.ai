# Brain Retrospective

## Increment 1 — Secure organisation boundary

### What worked

- The delivery verifier prevented the feature from being called DONE before evidence existed.
- Keeping authentication and organisation membership in one vertical slice avoided a fake identity boundary.
- CI caught packaging, lint and test defects before merge.

### What was wrong in the original estimate / plan

- F-01.01 was originally ordered before authentication even though its acceptance criteria required an authenticated owner. The dependency order was corrected before using a fake identity workaround.
- The backend package config relied on automatic setuptools discovery and failed once CI installed the package cleanly.
- Existing model tests assumed the original table set was permanent; adding `external_identities` correctly required updating the contract test.

### What was cut

- Nothing from S-01.01.01 or S-01.02.01 was cut.
- Full RBAC/ACL remains S-01.03.01; it was not silently absorbed into this increment.

### Process change

Before moving a story to READY, explicitly verify that every actor named in its acceptance criteria can already be authenticated/authorised by DONE dependencies. This becomes part of backlog refinement for future slices.
