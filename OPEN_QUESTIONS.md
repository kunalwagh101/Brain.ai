# Brain Open Questions

Only questions that can materially change product shape, security or cost belong here.

## OQ-001 Authentication provider — RESOLVED 2026-09-06
Decision: WorkOS AuthKit is the first managed authentication authority. FastAPI validates WorkOS access-token JWTs against provider JWKS and pins issuer/audience/RS256. Brain keeps its internal identity and permission model separate from the vendor so a later OIDC-compatible provider can be introduced without rewriting business-domain records.  
Reason: Brain is B2B/multi-tenant; WorkOS provides organisations, memberships, SSO/OIDC and role/permission support that match this boundary.  
Revisit trigger: measured product/customer requirement that WorkOS cannot satisfy, unacceptable unit economics, or provider availability/compliance issue.

## OQ-002 Slack private-message policy — RESOLVED 2026-09-06
Decision: Brain may ingest only Slack channels explicitly authorised by a workspace administrator. Public/shared channels still require explicit authorisation; private channels are opt-in; direct messages are excluded from the production MVP. Brain must preserve source visibility and apply its own tenant/resource ACL before retrieval.  
Reason: explicit opt-in is the smallest permission surface that still supports useful company memory without normalising employee surveillance or silently widening Slack visibility.  
Revisit trigger: a customer has a documented compliance/consent requirement for private-message ingestion and the connector, retention, audit and ACL design has been reviewed for that use case.

## OQ-003 Secrets manager — RESOLVED 2026-09-06
Decision: AWS Secrets Manager is the first production credential backend. PostgreSQL stores only the secret ARN/reference and non-secret connection metadata. Brain uses the AWS SDK credential chain and a small `SecretStore` contract so provider-specific connector code never persists OAuth/API tokens in application tables. Revocation first moves the connection out of ACTIVE state, then schedules secret deletion; connector workers may sync ACTIVE connections only.  
Reason: the planned production architecture is AWS-based, Secrets Manager provides managed encryption, IAM control, versioning and auditability, and this avoids inventing our own secret encryption/storage system.  
Revisit trigger: deployment moves to another cloud, customer-managed Vault/KMS is required, or measured cost/compliance constraints justify another backend.

## OQ-004 First meeting/document provider
Ambiguity: whether first evidence adapter targets Google Drive, Loom, Zoom/Meet transcript export, or generic upload.  
Recommended default: generic file/transcript ingestion first, then one customer-driven provider.  
Blast radius: OAuth scopes, file formats, transcription responsibility and storage cost.

## OQ-005 First AI provider policy
Ambiguity: which provider/model becomes the first production RAG generation default and what data-retention terms are required.  
Recommended default: provider-neutral gateway; choose the first model from measured eval quality/cost/latency and customer policy, not preference.  
Blast radius: eval baselines, compliance, cost and latency.

## OQ-006 Retention defaults
Ambiguity: the customer/legal default raw-event, derived-content and audit-log retention periods remain unresolved.  
Engineering-safe behavior: all three durations are configurable per organisation and `NULL` means no automatic age-based purge for that class. Brain does not invent a legal/compliance period when an organisation has not configured one.  
Recommended product default: obtain the customer's contractual/regulatory policy during onboarding, configure it explicitly, and separately align managed-database backup/PITR retention.  
Blast radius: storage cost, deletion design, compliance commitments and backup lifecycle.
