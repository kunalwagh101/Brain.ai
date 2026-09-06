# Definition of Ready / Definition of Done

## Definition of Ready

A story may enter `READY` only when all are true:

- acceptance criteria are written as machine-testable Given/When/Then outcomes;
- upstream dependencies are DONE or explicitly external and non-shape-changing;
- required data/contracts are known;
- no open question can materially change the story shape;
- security/privacy boundary is explicit;
- test strategy is known;
- migration/rollback impact is known when state changes;
- leading indicator and business value are identified.

## Definition of Done

A story may enter `DONE` only when all are true:

- [ ] production code implemented; no TODO/FIXME/NotImplemented/pass-stub/hardcoded production fixture inside the slice;
- [ ] each acceptance criterion has a named automated test or an explicitly justified non-automatable check;
- [ ] named test command was actually run for the evidence block and passed;
- [ ] negative paths cover validation, authn/authz, error handling and data integrity where relevant;
- [ ] concurrency/idempotency/transaction behaviour is tested where relevant;
- [ ] observability required to operate the slice exists without leaking secrets;
- [ ] accessibility is tested for user-facing UI changes;
- [ ] migration and rollback/forward-recovery notes exist when state changes;
- [ ] docs/CHANGELOG.md is updated;
- [ ] BOARD.md is updated;
- [ ] TRACEABILITY.md is updated;
- [ ] `python scripts/verify_board.py` passes;
- [ ] CI passes.

## Evidence block format

```text
EVIDENCE S-01.01.01
tests: backend/tests/test_organisations.py::test_cross_tenant_read_is_denied
command: cd backend && pytest tests/test_organisations.py -q
result: 4 passed (run YYYY-MM-DD)
code: backend/app/organisations.py:1-120
commit: <sha>
```

No resolvable evidence means the item stays `IN_REVIEW`; it cannot be called DONE.
