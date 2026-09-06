# Identity Resolution — Operator and Security Contract

## Purpose

Brain must connect provider actors to Brain users only when the evidence supports that attribution. A source identity is an observed Slack/GitHub identity inside one Brain organisation. It is deliberately separate from WorkOS authentication identity.

## Automatic resolution policy

Automatic resolution is fail-closed. It is allowed only when all conditions are true:

1. the provider actor has a stable provider external ID
2. the identity belongs to the current Brain organisation
3. the email evidence is explicitly provider-verified
4. the normalized email exactly matches an active Brain user
5. that user has an active membership in the same Brain organisation
6. the identity is not already in `REVIEW_REQUIRED` because of contradictory verified evidence

The resolver must not use display-name matching, fuzzy username matching, company-domain matching, cross-tenant data or an LLM/model guess.

## Resolution states

- `UNRESOLVED`: Brain has source evidence but insufficient trustworthy evidence to identify a Brain user.
- `RESOLVED`: the source identity currently points to a Brain user by deterministic verified evidence or an authorised manual decision.
- `REVIEW_REQUIRED`: contradictory verified evidence was observed; automatic attribution is cleared until an administrator resolves the conflict.

Unresolved is a valid state and must not be converted into a guess for convenience.

## Manual administration

Only roles with `identity.manage` may list/manage source identities. In the current role matrix this is Owner/Admin.

Manual resolve/reassign:

- target user must be active
- target user must be a member of the same organisation
- previous/new user IDs, action, method, administrator and bounded evidence/reason are stored in immutable resolution history
- all canonical events linked to that source identity receive the current `resolved_user_id`
- provider actor fields on canonical events are not rewritten

Manual unresolve clears `resolved_user_id` from the source identity and its linked canonical events while preserving source identity observations and resolution history.

## Reconciliation

The reconciliation endpoint is for canonical events created before the identity layer existed. It processes only canonical person actors in the requested organisation that do not yet have a `source_identity_id`. Re-running it is safe because source identity uniqueness is `(organization_id, provider, external_id)` and observations are unique per canonical event.

## Privacy and tenant isolation

Source identities never resolve across organisations. A same-email user in another organisation is not evidence for the current tenant. Source evidence and resolution history must be treated as company data and exposed only through authorised APIs/UI.

Do not log provider tokens, secret values, message content or unnecessary PII in resolution audit evidence.

## Operational checks

Operators should monitor:

- unresolved identity count by provider
- `REVIEW_REQUIRED` count
- manual reassign/unresolve rate
- reconciliation backlog
- identity-resolution errors

Do not turn these metrics into employee productivity scoring.

## Migration / rollback

Revision `20260906_0007` adds source identity tables and optional canonical identity links.

Before downgrade:

1. stop canonicalisation/reconciliation and any downstream consumer relying on identity links
2. export resolution history if required for investigation/audit
3. deploy code compatible with revision `20260906_0006`
4. downgrade the migration

The downgrade removes identity-resolution state and canonical links. Original raw events and canonical provider actor evidence remain available for reconstruction.
