# Brain Open Questions

Only questions that can materially change product shape, security or cost belong here.

## OQ-001 Authentication provider
Ambiguity: which identity provider is the first production auth authority?  
Options: WorkOS/Auth0/Clerk/custom OIDC.  
Recommended default: standards-based OIDC adapter with one managed provider first; avoid custom password auth.  
Blast radius if wrong: user/session schema, SSO roadmap, tenant provisioning and security controls.

## OQ-002 Slack private-message policy
Ambiguity: whether Brain may ingest DMs/private channels and under whose consent/policy.  
Options: public/shared channels only; private channels opt-in; DMs excluded; enterprise compliance ingestion where contractually authorised.  
Recommended default: channels explicitly authorised by workspace admins; exclude DMs from MVP.  
Blast radius: permissions model, trust, privacy/compliance and connector scopes.

## OQ-003 Secrets manager
Ambiguity: first production secrets backend.  
Options: AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, Vault.  
Recommended default: deployment-cloud native secret manager behind a tiny reference interface.  
Blast radius: integration credential lifecycle and deployment infrastructure.

## OQ-004 First meeting/document provider
Ambiguity: whether first evidence adapter targets Google Drive, Loom, Zoom/Meet transcript export, or generic upload.  
Recommended default: generic file/transcript ingestion first, then one customer-driven provider.  
Blast radius: OAuth scopes, file formats, transcription responsibility and storage cost.

## OQ-005 First AI provider policy
Ambiguity: which provider/model becomes the first production RAG generation default and what data-retention terms are required.  
Recommended default: provider-neutral gateway; choose the first model from measured eval quality/cost/latency and customer policy, not preference.  
Blast radius: eval baselines, compliance, cost and latency.

## OQ-006 Retention defaults
Ambiguity: default raw-event, derived-content and audit-log retention periods.  
Recommended default: configurable per organisation; do not hard-code a legal/compliance duration without customer/regulatory evidence.  
Blast radius: storage cost, deletion design, compliance commitments and backup lifecycle.
