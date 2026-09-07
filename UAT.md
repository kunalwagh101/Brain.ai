# Brain User Acceptance Testing

`DONE` on the engineering board means the implementation is complete in the repository and has passed automated verification. It does **not** mean the feature has been accepted with realistic customer data.

A feature may be called **PASSED / ACCEPTED** only after both of the following are recorded:

1. **Real-data backend validation** — realistic data is exercised through the deployed/backend API and expected records, permissions, errors, migrations and side effects are manually checked.
2. **Frontend/manual workflow validation** — the user runs the actual UI flow, enters realistic data, checks loading/empty/error/success states, and confirms the end-to-end result.

Until both are recorded, external status is `UAT_PENDING` even if CI is green.

| Feature | Engineering status | Real-data backend | Frontend/manual | Acceptance |
|---|---|---|---|---|
| F-01.01 Organisation & Identity | DONE | PENDING | PENDING | UAT_PENDING |
| F-01.02 Authentication | DONE | PENDING | PENDING | UAT_PENDING |
| F-01.03 RBAC + Resource ACL | DONE | PENDING | PENDING | UAT_PENDING |
| F-02.01 Integration Framework | DONE | PENDING | PENDING | UAT_PENDING |
| F-02.02 Slack Connector | DONE | PENDING | PENDING | UAT_PENDING |
| F-02.03 GitHub Connector | DONE | PENDING | PENDING | UAT_PENDING |
| F-03.01 Raw Event Ingestion | DONE | PENDING | PENDING | UAT_PENDING |
| F-03.02 Canonical Event Model | DONE | PENDING | PENDING | UAT_PENDING |
| F-03.03 Identity Resolution | DONE | PENDING | PENDING | UAT_PENDING |
| F-04.01 Work Graph | DONE | PENDING | PENDING | UAT_PENDING |
| F-04.02 Decision & Blocker Memory | BLOCKED | PENDING | PENDING | UAT_PENDING |
| F-05.01 Permission-Aware Retrieval | IN_REVIEW | PENDING | PENDING | UAT_PENDING |

Detailed scripts live under `UAT/`.

When UAT is performed, append the environment, data set description, steps, observed result, defects found/fixed, tester, date and final ACCEPTED/REJECTED decision. Do not store production secrets or sensitive customer data in this file.