# Brain Traceability

This file is the engineering evidence index. A row is completed only after its story is engineering-DONE and has a resolvable evidence block. Real-data/manual feature acceptance is tracked separately in `UAT.md` and feature-specific UAT files.

| Story | Epic | Requirement / outcome | Tests | Code | Status |
|---|---|---|---|---|---|
| S-01.01.01 | E-01 | organisation membership + tenant boundary | backend/tests/test_organizations.py | backend/app/routes/organizations.py | DONE |
| S-01.02.01 | E-01 | real authentication | backend/tests/test_auth.py | backend/app/auth.py | DONE |
| S-01.03.01 | E-01 | RBAC/ACL before retrieval | backend/tests/test_permissions.py + backend/tests/test_organizations.py | backend/app/permissions.py + backend/app/routes/organizations.py | DONE |
| S-02.01.01 | E-02 | scoped integration lifecycle | backend/tests/test_integrations.py + backend/tests/test_secrets.py | backend/app/routes/integrations.py + backend/app/secrets.py | DONE |
| S-02.02.01 | E-02 | Slack ingestion | backend/tests/test_slack.py | backend/app/routes/slack_oauth.py + backend/app/routes/slack_channels.py + backend/app/routes/slack_webhooks.py | DONE |
| S-02.03.01 | E-02 | GitHub ingestion | backend/tests/test_github_connector.py | backend/app/routes/github_oauth.py + backend/app/routes/github_webhooks.py + backend/app/routes/github_backfill.py | DONE |
| S-02.04.01 | E-02 | meeting/document evidence | backend/tests/test_evidence_ingestion.py + backend/tests/test_ask_brain_generic_evidence.py + backend/tests/test_decision_memory_generic_evidence.py + UAT/F-02.04.md | backend/app/evidence_models.py + backend/app/evidence_ingestion.py + backend/app/routes/evidence.py + backend/migrations/versions/20260910_0017_generic_evidence_sources.py + docs/GENERIC_EVIDENCE.md | IN_REVIEW |
| S-03.01.01 | E-03 | raw durable/idempotent ingestion | backend/tests/test_raw_events.py + backend/tests/test_slack.py | backend/app/raw_events.py + backend/app/models.py | DONE |
| S-03.02.01 | E-03 | canonical event model | backend/tests/test_canonical_events.py + backend/tests/test_github_connector.py | backend/app/canonical_events.py + backend/app/models.py | DONE |
| S-03.03.01 | E-03 | tenant-safe identity resolution | backend/tests/test_identity_resolution.py + backend/tests/test_canonical_events.py | backend/app/identity_resolution.py + backend/app/routes/identities.py + backend/app/canonical_events.py | DONE |
| S-04.01.01 | E-04 | typed tenant-safe work graph | backend/tests/test_work_graph.py | backend/app/work_graph.py + backend/app/routes/work_graph.py | DONE |
| S-04.02.01 | E-04 | decision/blocker memory | backend/tests/test_decision_memory.py + backend/tests/test_decision_memory_evaluation.py + backend/tests/test_decision_memory_generic_evidence.py + UAT/F-04.02.md | backend/app/decision_memory.py + backend/app/routes/decision_memory.py + backend/app/decision_memory_worker.py | BLOCKED |
| S-05.01.01 | E-05 | authenticated permission-aware retrieval | backend/tests/test_auth.py + backend/tests/test_permissions.py + backend/tests/test_organizations.py + backend/tests/test_search.py + backend/tests/test_search_evaluation.py + backend/tests/test_search_contract.py + backend/tests/test_acceptance_chain.py + UAT/F-05.01.md | backend/app/auth.py + backend/app/search.py + backend/app/routes/search.py + backend/app/search_worker.py + backend/run_acceptance_chain.py + backend/Dockerfile.staging + render.yaml + docs/RENDER_STAGING.md | DONE |
| S-05.02.01 | E-05 | evidence-backed Ask Brain | backend/tests/test_ask_brain.py + backend/tests/test_ask_brain_routes.py + backend/tests/test_ask_brain_citations.py + backend/tests/test_ask_brain_limits.py + backend/tests/test_ask_brain_evaluation.py + backend/tests/test_ask_brain_generic_evidence.py + backend/tests/test_ask_brain_contract_hardening.py + backend/tests/test_runtime_discovery.py + backend/tests/test_ai_cached_cost.py + backend/tests/test_ai_cost_routes.py + UAT/F-05.02.md | backend/app/ask_brain.py + backend/app/routes/ask_brain.py + backend/app/ask_brain_evaluation.py + backend/app/routes/runtime_discovery.py + backend/run_acceptance_chain.py + scripts/run-ask-brain-evaluation.py + scripts/score-ask-brain-review.py + scripts/configure-ask-brain-openai.py + app/brain-api.ts + app/brain-bff.ts + app/ask-brain-panel.tsx + docs/ASK_BRAIN_STAGING.md + docs/WORKOS_FRONTEND_ACCEPTANCE.md | BLOCKED |
| S-06.01.01 | E-06 | governed AI gateway | backend/tests/test_ai_gateway.py + backend/tests/test_ai_gateway_adapter.py + backend/tests/test_ai_gateway_routes.py + backend/tests/test_ai_cached_cost.py + backend/tests/test_ai_provider_credentials.py | backend/app/ai_provider_registry.py + backend/app/ai_provider_adapter.py + backend/app/ai_provider_credentials.py + backend/app/routes/ai_gateway.py + backend/app/routes/ai_provider_credentials.py | DONE |
| S-06.02.01 | E-06 | AI/API usage and budgets | backend/tests/test_ai_usage.py + backend/tests/test_ai_usage_reconciliation.py + backend/tests/test_ai_cached_cost.py + backend/tests/test_ai_cost_routes.py | backend/app/ai_usage.py + backend/app/ai_usage_models.py + backend/app/ai_usage_reconciliation.py + backend/app/routes/ai_usage.py + backend/migrations/versions/20260910_0016_ai_cached_input_cost.py | BLOCKED |
| S-06.03.01 | E-06 | external API credential registry | backend/tests/test_api_registry.py + backend/tests/test_api_registry_worker.py + backend/tests/test_api_registry_usage_route.py + backend/tests/test_secrets.py | backend/app/api_registry.py + backend/app/routes/api_registry.py + backend/app/routes/api_registry_usage.py + backend/app/api_registry_worker.py | IN_REVIEW |
| S-07.01.01 | E-07 | evidence-backed deterministic project command centre | backend/tests/test_project_status.py + backend/tests/test_project_status_routes.py + UAT/F-07.01.md | backend/app/project_status_models.py + backend/app/project_status.py + backend/app/routes/project_status.py + backend/migrations/versions/20260910_0018_project_status.py + app/production-executive-workspace.tsx + app/live-workspace.tsx + docs/PROJECT_STATUS.md | BLOCKED |
| S-07.02.01 | E-07 | permission-aware evidence-backed executive overview | backend/tests/test_executive_overview.py + backend/tests/test_executive_overview_budget_permissions.py + backend/tests/test_executive_overview_memory.py + backend/tests/test_api_registry_usage_route.py + UAT/F-07.02.md | backend/app/executive_overview.py + backend/app/routes/executive_overview.py + backend/app/routes/api_registry_usage.py + app/production-executive-workspace.tsx + app/live-workspace.tsx + docs/EXECUTIVE_OVERVIEW.md + docs/WORKOS_FRONTEND_ACCEPTANCE.md + docs/planning/increment-21.md | BLOCKED |
| S-08.01.01 | E-08 | governed agent runtime | pending | pending | BLOCKED |
| S-09.01.01 | E-09 | production observability and SLOs | backend/tests/test_observability.py | backend/app/observability.py + backend/app/health.py + backend/app/integrations.py + backend/app/raw_events.py + backend/app/ai_provider_registry.py | IN_REVIEW |
| S-09.02.01 | E-09 | audit/retention/deletion | backend/tests/test_data_governance.py + backend/tests/test_data_governance_routes.py + backend/tests/test_data_governance_worker.py + backend/tests/test_data_governance_retained_raw.py + backend/tests/test_data_governance_audit.py + backend/tests/test_direct_messages.py | backend/app/data_governance.py + backend/app/data_governance_models.py + backend/app/data_governance_worker.py + backend/app/routes/data_governance.py + backend/app/security_audit.py + backend/app/canonical_events.py + backend/migrations/versions/20260916_0023_private_message_retention.py | DONE |
| S-09.03.01 | E-09 | CI/deploy/rollback/restore | backend/tests/test_release_contract.py + backend/tests/test_database_url.py + backend/tests/test_acceptance_chain.py + UAT/F-09.03.md | .github/workflows/release-gate.yml + backend/Dockerfile.staging + backend/run_acceptance_chain.py + scripts/postgres-backup.sh + scripts/postgres-restore.sh + render.yaml + backend/app/database.py + docs/DEPLOYMENT.md + docs/RENDER_STAGING.md | BLOCKED |
| S-09.04.01 | E-09 | latency/cost benchmarks | backend/tests/test_performance_budget.py + backend/tests/test_ai_cached_cost.py + UAT/F-09.04.md | backend/app/performance_budget.py + scripts/run-performance-benchmark.py + ops/performance/budgets.json + .github/workflows/performance-gate.yml + docs/PERFORMANCE.md | BLOCKED |
| S-10.01.01 | E-10 | native tracks/chat | `backend/tests/test_native_chat.py`; `tests/workspace-contract.test.mjs` | Native channel API, evidence projection, restricted membership and workspace UI | DONE |
| S-10.02.01 | E-10 | workspace shell/navigation | `backend/tests/test_workspace_navigation.py`; `tests/workspace-contract.test.mjs` | Permission-aware workspace shell | BLOCKED |
| S-10.03.01 | E-10 | live intelligence surfaces | `tests/workspace-contract.test.mjs` | Live project, memory, overview and Ask Brain composition | BLOCKED |
| S-10.04.01 | E-10 | production frontend auth/BFF | `tests/workspace-contract.test.mjs` | Reviewed WorkOS activation templates | BLOCKED |
| S-10.05.01 | E-10 | evidence/files workspace | `backend/tests/test_evidence_workspace.py`; `tests/workspace-contract.test.mjs` | Governed evidence UI and BFF contracts | BLOCKED |
| S-10.06.01 | E-10 | conversation UX | `backend/tests/test_native_chat.py` + `backend/tests/test_native_conversation.py` + `backend/tests/test_observability.py` + `tests/workspace-contract.test.mjs` | `backend/app/native_chat.py` + `backend/app/native_conversation.py` + conversation models/routes/migration + `app/native-chat-panel.tsx` + typed API/BFF/WorkOS route templates | DONE |
| S-10.06.02 | E-10 | participant-safe direct messages | `backend/tests/test_direct_messages.py` + `backend/tests/test_direct_message_epochs.py` + `tests/direct-message-contract.test.mjs` + `UAT/F-10.06.02.md` | `backend/app/direct_message_models.py` + `backend/app/direct_messages.py` + `backend/app/routes/direct_messages.py` + migrations `20260916_0022`/`0023`/`0024` + `app/direct-message-api.ts` + `app/direct-message-bff.ts` + `app/direct-message-panel.tsx` + WorkOS DM route templates | DONE |
| S-10.07.01 | E-10 | developer/agent workspace | `backend/tests/test_agent_workspace.py` + `tests/agent-workspace-contract.test.mjs` + `UAT/F-10.07.md` | `backend/app/agent_workspace.py` + `backend/app/agent_workspace_models.py` + agent-workspace routes + `app/agent-workspace-api.ts` + `app/agent-workspace-bff.ts` + `app/agent-workspace-panel.tsx` + WorkOS agent route templates | IN_REVIEW |
| S-10.08.01 | E-10 | workspace administration | `backend/tests/test_admin_center.py` + `backend/tests/test_membership_governance.py` + `backend/tests/test_ai_provider_credentials.py` + `tests/admin-center-contract.test.mjs` + `UAT/F-10.08.md` | admin-center backend/API + membership governance routes + `backend/app/ai_provider_credentials.py` + `backend/app/routes/ai_provider_credentials.py` + `app/admin-center-api.ts` + `app/admin-center-bff.ts` + `app/admin-center-panel.tsx` + WorkOS admin action template | IN_REVIEW |
| S-10.09.01 | E-10 | personal Activity & Notifications inbox | `backend/tests/test_activity.py` + `backend/tests/test_activity_inbox.py` + `tests/activity-contract.test.mjs` + `UAT/F-10.09.md` | `backend/app/activity.py` + `backend/app/activity_inbox.py` + activity models/routes + migrations `20260918_0025`/`0026`/`0027` + `app/activity-api.ts` + `app/activity-bff.ts` + `app/activity-panel.tsx` + `app/activity-dock.tsx` + WorkOS Activity route templates | IN_REVIEW |
| S-10.10.01 | E-10 | live workspace updates | `tests/live-updates-contract.test.mjs` + `UAT/F-10.10.md` | `app/live-updates-api.ts` + `app/live-updates-bff.ts` + `app/live-workspace-refresh.tsx` + `app/native-chat-panel.tsx` + `app/production-workspace.tsx` + WorkOS live route template/activation | IN_REVIEW |
| S-10.11.01 | E-10 | workspace search & quick switcher | `backend/tests/test_workspace_search.py` + `backend/tests/test_native_conversation.py::test_single_message_read_respects_current_channel_access` + `tests/workspace-search-contract.test.mjs` + `UAT/F-10.11.md` | existing S-05.01 Search API + `app/workspace-search-bff.ts` + `app/workspace-search.tsx` + exact native-message read/deep-link path + WorkOS search route template/activation | IN_REVIEW |
| S-10.12.01 | E-10 | author-safe message edit/retract lifecycle | `backend/tests/test_message_lifecycle.py` + `tests/message-lifecycle-contract.test.mjs` + `UAT/F-10.12.md` | revisioned `NativeMessage` + append-only `NativeMessageRevision` evidence links + immutable lifecycle RawEvent/CanonicalEvent revisions + retired SearchDocument versions + current-permission mutation API/BFF/UI + governed revision retention | IN_REVIEW |
| S-10.13.01 | E-10 | governed channel file attachments | `backend/tests/test_channel_attachments.py` + `tests/channel-attachments-contract.test.mjs` + `UAT/F-10.13.md` | existing EvidenceSource ingestion + native channel scope + `NativeMessageAttachment` references + live channel permission/grant propagation + bounded WorkOS multipart BFF + retry-safe root/thread composer + migration `20260918_0030` | IN_REVIEW |
| S-10.14.01 | E-10 | ephemeral authorised presence & typing | `backend/tests/test_collaboration_presence.py` + `tests/collaboration-presence-contract.test.mjs` + `UAT/F-10.14.md` | short-lived PostgreSQL presence/typing leases + current channel/DM permission rechecks + audit-free FastAPI route + same-origin WorkOS BFF + visible-tab heartbeat + throttled focused-composer typing UI + migration `20260919_0031` | IN_REVIEW |
| S-10.15.01 | E-10 | shared channel message pins | `backend/tests/test_channel_pins.py` + `tests/channel-pins-contract.test.mjs` + `UAT/F-10.15.md` | reference-only `NativeMessagePin` + current reader/writer checks + same-lifecycle retract cleanup + typed API/BFF + server-rendered Pins panel + structural live invalidation + migration `20260919_0032` | IN_REVIEW |
| S-10.16.01 | E-10 | private personal saved channel messages | `backend/tests/test_saved_messages.py` + `tests/saved-messages-contract.test.mjs` + `UAT/F-10.16.md` | reference-only `NativeMessageSave` + membership/message scoped FKs + current visible-channel filtering + audit-free personal API/BFF + same-lifecycle retract cleanup + exact deep-link Saved UI + migration `20260919_0033` | IN_REVIEW |
| S-10.17.01 | E-10 | first-unread divider and exact jump | `backend/tests/test_native_conversation.py` + `backend/tests/test_message_lifecycle.py` + `tests/first-unread-contract.test.mjs` + `UAT/F-10.17.md` | set-based first-unread summary over existing read cursor + permission-aware same-origin exact-message GET + stable accessible root/thread divider and jump UI | IN_REVIEW |
| S-10.18.01 | E-10 | participant-only DM unread and resume | `backend/tests/test_direct_message_unread.py` + `tests/direct-message-unread-contract.test.mjs` + `UAT/F-10.18.md` | per-participant epoch-clamped DM read cursors + set-based unread/first-target summary + exact participant-only message read + same-origin divider/jump UI + migration `20260919_0034` | IN_REVIEW |
| S-10.19.01 | E-10 | stable older-message pagination | `backend/tests/test_native_conversation.py::test_native_root_history_uses_stable_sequence_cursor` + `backend/tests/test_direct_messages.py::test_direct_message_history_uses_sequence_cursor` + `tests/conversation-pagination-contract.test.mjs` + `UAT/F-10.19.md` | existing channel/DM sequence columns + bounded before_sequence list APIs/BFF GET + merge-safe accessible Load older controls; no migration | IN_REVIEW |
| S-10.20.01 | E-10 | author-owned participant-private DM lifecycle | `backend/tests/test_direct_message_lifecycle.py` + `tests/direct-message-lifecycle-contract.test.mjs` + `UAT/F-10.20.md` | revisioned/tombstoned `DirectMessage` + private append-only `DirectMessageRevision` + author/current-epoch optimistic concurrency + same-origin lifecycle UI + migration `20260919_0035` | IN_REVIEW |
| S-10.21.01 | E-10 | stable thread-reply history pagination | `backend/tests/test_native_conversation.py::test_thread_reply_history_uses_stable_sequence_cursor` + `tests/thread-pagination-contract.test.mjs` + `UAT/F-10.21.md` | existing NativeMessage sequence + bounded before_sequence reply GET/BFF + merge-safe Load older replies and live refresh; no migration | IN_REVIEW |
| S-10.22.01 | E-10 | independent per-thread unread and resume | `backend/tests/test_native_conversation.py::test_thread_unread_state_is_independent_monotonic_and_excludes_own_replies` + `backend/tests/test_native_conversation.py::test_retracted_reply_is_removed_from_thread_unread_attention` + `tests/thread-unread-contract.test.mjs` + `UAT/F-10.22.md` | tenant/root/user scoped NativeThreadReadState + set-based unread/first-target summaries + monotonic thread-read route + root badge/divider/jump UI + migration `20260920_0036` | IN_REVIEW |
| S-10.23.01 | E-10 | participant-private DM reactions | `backend/tests/test_direct_message_reactions.py` + `tests/direct-message-reaction-contract.test.mjs` + `UAT/F-10.23.md` | private DirectMessageReaction rows + participant/current-epoch idempotent mutations + batch aggregate count/reacted-by-me read model + same-origin WorkOS UI + migration `20260920_0037` | IN_REVIEW |
| S-10.24.01 | E-10 | navigation-only Workspace Teams | `backend/tests/test_native_workspace.py::test_team_lifecycle_is_tenant_scoped_revisioned_and_manager_only` + `backend/tests/test_native_workspace.py::test_team_metadata_never_changes_channel_or_resource_grants` + `backend/tests/test_native_workspace.py::test_team_creation_rolls_back_when_audit_persistence_fails` + `tests/native-teams-contract.test.mjs` + `UAT/F-10.24.md` | NativeTeam revisioned metadata + creator/Owner/Admin lifecycle + atomic Team/audit transaction + server-loaded Team navigation + Unassigned channels fallback + same-origin WorkOS mutations + migration `20260920_0038` | DONE |
| S-10.25.01 | E-10 | Team channel groups with ACL-neutral channel placement | `backend/tests/test_native_workspace.py::test_channel_group_moves_preserve_acl_and_resource_grants` + `backend/tests/test_native_workspace.py::test_channel_group_team_scope_and_stale_revision_fail_closed` + `backend/tests/test_native_workspace.py::test_channel_group_and_navigation_roll_back_when_audit_persistence_fails` + `tests/native-channel-groups-contract.test.mjs` + `UAT/F-10.25.md` | NativeChannelGroup revisioned metadata + nullable NativeChannel team/group navigation refs + channel/Team-manager assignment gate + atomic group/navigation audit transaction + nested Team/Ungrouped/Unassigned UI + same-origin WorkOS routes + migration `20260920_0039` | DONE |
| S-10.26.01 | E-10 | channel identity/lifecycle/restricted-member administration | `backend/tests/test_native_workspace.py::test_channel_administration_is_revisioned_read_only_when_archived_and_syncs_track` + `backend/tests/test_native_workspace.py::test_restricted_member_access_updates_membership_and_resource_grants_consistently` + `backend/tests/test_native_workspace.py::test_channel_settings_and_member_access_roll_back_when_audit_fails` + `tests/channel-administration-contract.test.mjs` + `UAT/F-10.26.md` | optimistic channel settings revision + current Work Graph identity sync + archive/read-only/restore lifecycle + existing member read/write grant propagation + atomic business/audit rollback + same-origin WorkOS settings/UI + migration `20260920_0040` | DONE |

EVIDENCE S-01.01.01
tests: backend/tests/test_organizations.py::test_cross_tenant_organization_read_returns_not_found
command: cd backend && pytest -q
result: 14 passed (GitHub Actions run 34027972498, 2026-09-06)
code: backend/app/routes/organizations.py
commit: b53d3185000da2ebf05d730a07cb899917165707

EVIDENCE S-01.02.01
tests: backend/tests/test_auth.py::test_verify_access_token_validates_signature_and_claims
command: cd backend && pytest -q
result: 14 passed (GitHub Actions run 34027972498, 2026-09-06)
code: backend/app/auth.py
commit: b53d3185000da2ebf05d730a07cb899917165707

Historical note: the S-01.02.01 evidence above is tied to its recorded commit. The current branch subsequently hardened the WorkOS AuthKit token contract to validate `client_id`, optional explicit custom `aud`, exact issuer/expiry/signature and the required `urn:brain:user_email` JWT Template claim while refusing to identify the subject from optional `act` actor context. Those later changes are included in the active S-05.01 acceptance stage and are **not** claimed as newly passing until that stage executes successfully with synthetic and real WorkOS evidence.

EVIDENCE S-01.03.01
tests: backend/tests/test_permissions.py::test_resource_dependency_denies_before_endpoint_body
command: cd backend && pytest -q
result: 34 passed (GitHub Actions run 34031342636, 2026-09-06)
code: backend/app/permissions.py
commit: 65d0fbc4a3d843e81c1bd036febe7749a9409a8d

EVIDENCE S-02.01.01
tests: backend/tests/test_integrations.py::test_admin_creates_connection_without_persisting_plaintext_credentials
command: cd backend && pytest -q
result: 46 passed (GitHub Actions run 34032491893, 2026-09-06)
code: backend/app/routes/integrations.py
commit: 906985fad5c5cbf8a5419d94f3200cef0b259ae7

EVIDENCE S-02.02.01
tests: backend/tests/test_slack.py::test_signed_authorized_event_is_stored_once_with_exact_payload
command: cd backend && pytest -q
result: 62 passed (GitHub Actions run 34034605245, 2026-09-06)
code: backend/app/routes/slack_webhooks.py
commit: e75d9864fcf81331d332ae8a6959b79650887299

EVIDENCE S-03.01.01
tests: backend/tests/test_raw_events.py::test_raw_event_preserves_exact_bytes_and_checksum
command: cd backend && pytest -q
result: 62 passed (GitHub Actions run 34034605245, 2026-09-06)
code: backend/app/raw_events.py
commit: e75d9864fcf81331d332ae8a6959b79650887299

EVIDENCE S-02.03.01
tests: backend/tests/test_github_connector.py::test_signed_private_repo_webhook_is_exactly_once_and_acl_preserved
command: cd backend && pytest -q
result: 73 passed (GitHub Actions run 34037248953, 2026-09-06)
code: backend/app/routes/github_webhooks.py
commit: 59155580a3e743309d2b9cbeff83d324ef1bf053

EVIDENCE S-03.02.01
tests: backend/tests/test_canonical_events.py::test_slack_backfill_message_maps_to_versioned_canonical_event
command: cd backend && pytest -q
result: 73 passed (GitHub Actions run 34037248953, 2026-09-06)
code: backend/app/canonical_events.py
commit: 59155580a3e743309d2b9cbeff83d324ef1bf053

EVIDENCE S-03.03.01
tests: backend/tests/test_identity_resolution.py::test_verified_exact_email_auto_resolves_only_same_org_member
command: cd backend && pytest -q
result: 82 passed (GitHub Actions run 34039308232, 2026-09-06)
code: backend/app/identity_resolution.py + backend/app/routes/identities.py + backend/app/canonical_events.py
commit: be307d8b26bf97fa2ae8eaad52b1a370885a3123

EVIDENCE S-04.01.01
tests: backend/tests/test_work_graph.py::test_private_slack_graph_uses_current_membership_not_historical_acl
command: cd backend && pytest -q
result: 89 passed (GitHub Actions run 34043847195, 2026-09-06)
code: backend/app/work_graph.py + backend/app/routes/work_graph.py + backend/app/work_graph_models.py
commit: a97d724416191ec8515f5ed90888321343013cda

S-02.04.01 intentionally has no EVIDENCE block yet. Generic governed file/transcript ingestion, immutable source hashing, bounded extraction/chunking, RawEvent/CanonicalEvent/Work Graph/Search projection, live ACL reuse, source deletion, migration `20260910_0017`, docs, UAT and cross-feature regression contracts are staged. The ordered acceptance runner now places this stage immediately after S-05.01. No executable PostgreSQL/real-data/browser PASS is claimed, so the story remains IN_REVIEW.

S-05.01.01 is engineering-DONE on commit `af9358c5f6d20079160c7fa77c4d771772d54703`. Permission filtering is applied in the shared Search base query before keyword or semantic result selection; revoked/deleted evidence disappears; every returned result preserves provenance; synthetic recall-at-3 is gated at >=90%. Fresh Backend CI rerun passed Ruff and all 384 backend tests. Delivery Verifier and Release Gate also pass on the same code commit. Realistic deployed/authenticated browser acceptance remains UAT_PENDING.

S-05.02.01 intentionally has no EVIDENCE block yet. OQ-005 is resolved to OpenAI API with `gpt-5.6-terra` as the first conditional production candidate. S-05.01 is now engineering-DONE. The branch stages permission-aware/no-evidence retrieval, governed explicit provider/model execution, fail-closed grounding, exact JSON output, bounded citations, generic meeting/document evidence, runtime discovery, two-phase evaluation, cache-aware exact cost and the ordered acceptance stage including gateway/cost dependencies. Real provider compatibility/cost smoke, >=90% representative retrieval evaluation, >=98% human-reviewed citation correctness, p95 <10s and authenticated WorkOS browser UAT remain external acceptance blockers, so S-05.02 remains BLOCKED.

S-04.02.01 intentionally has no EVIDENCE block yet. Its S-05.01 dependency is now engineering-DONE. The deterministic candidate extractor, permission-aware reads, human review history, generic meeting/document path and evaluation contracts are staged. Human-reviewed/reopened candidates are protected from machine supersession/rewrites and review mutations lock the candidate row. Representative >=90% precision evaluation and realistic UAT have not run, so the story remains BLOCKED.

S-07.01.01 intentionally has no EVIDENCE block yet. The branch stages structured project-progress persistence, deterministic weighted progress, permission-aware Work Graph evidence traversal intersected with Search authorization, separate confirmed decision/blocker vs candidate-memory views, audit-backed progress mutation, APIs, migration `20260910_0018`, tests/docs/UAT and a live frontend renderer. The ordered acceptance runner places Project Command Centre after Decision Memory. S-04.02 is not engineering-DONE and no real backend/permission/frontend UAT has executed, so S-07.01 remains BLOCKED.

S-07.02.01 intentionally has no EVIDENCE block yet. The branch stages an `audit.read` executive read model over visible projects, confirmed memory, exact/incomplete AI spend/budgets and trusted external API usage. Metric provenance and Work Graph budget privacy are explicit; API monetary cost is unavailable rather than guessed; no employee productivity/worth score field exists. Backend contracts, live frontend renderer, WorkOS acceptance documentation and UAT are staged, but S-07.01 and S-06.02 are not DONE and no executable reconciliation/permission/browser acceptance has run. S-07.02 remains BLOCKED.

S-06.01.01 is engineering-DONE on commit `af9358c5f6d20079160c7fa77c4d771772d54703`. The gateway records organisation/user/provider/model plus visible attribution node when supplied, surfaces provider failures as bounded safe codes, stores only secret references in provider configuration and excludes prompt/completion/credential material from operational logs. Fresh Backend CI rerun passed Ruff and all 384 backend tests. Real-provider compatibility and operator/browser acceptance remain UAT_PENDING.

S-06.02.01 intentionally has no EVIDENCE block yet. S-06.01 is now engineering-DONE. The usage ledger models ordinary/cached/output token usage and optional cached pricing. Invalid/missing required billing dimensions fail closed to `unknown`, and request-scoped cost audit supports independent recomputation. Real provider usage/cost reconciliation remains an external acceptance blocker, so S-06.02 remains BLOCKED.

S-10.01.01 is engineering-DONE. Release Gate `35789299001` passed native-channel authorization/persistence/evidence projection regressions, the production frontend build/source contracts, repository verifier and PostgreSQL migration recovery on code commit `10a9028685f67ec6db923d3371a67df13276d044`. Board, traceability, changelog and UAT records are now aligned; authenticated WorkOS/browser UAT remains `UAT_PENDING`.

S-06.03.01 intentionally has no EVIDENCE block yet. Tenant-scoped API service/grant inventory, secret-reference lifecycle, owner/scope/environment history, rotation, fail-closed revocation, expiry cleanup, internal usage observation, tests/docs/UAT and Executive Overview API-usage drill-down are staged. Relevant API registry contracts run in the Executive Overview acceptance stage. Executable verification remains outstanding, so the story remains IN_REVIEW.

S-09.01.01 intentionally has no EVIDENCE block yet. Structured JSON logging/redaction, bounded Prometheus metrics, OpenTelemetry tracing, PostgreSQL readiness telemetry, connector/AI instrumentation, protected metrics access, SLO alert rules, incident runbook, tests and deployed-UAT instructions are staged. No new executable pass is claimed; the story remains IN_REVIEW.

S-09.02.01 is engineering-DONE on commit `af9358c5f6d20079160c7fa77c4d771772d54703`. Audit event keys are content-stable/idempotent, PostgreSQL rejects audit updates, retention classes are independently configurable, legal hold blocks purge/deletion, deletion removes or tombstones derived retrieval material and records completion evidence, and stale deletion work is recoverable. Fresh Backend CI rerun passed Ruff and all 384 backend tests; Release Gate passed PostgreSQL upgrade/downgrade/forward recovery plus backup/restore. Deployed customer-policy UAT remains UAT_PENDING.

S-09.03.01 intentionally has no EVIDENCE block yet. A provider-neutral Release Gate, Alembic upgrade/downgrade/forward-recovery exercise, production container readiness smoke, PostgreSQL backup/restore, restored-data sentinel verification, release manifest, Render Blueprint and the new ordered staging acceptance chain are staged. GitHub-hosted runners still fail allocation before step execution and no real Render deploy/rollback/restore exercise is yet recorded. OQ-007 production topology remains open, so S-09.03 remains BLOCKED.

S-09.04.01 intentionally has no EVIDENCE block yet. Deterministic percentile/budget evaluation, versioned core/search/AI workload, deployed HTTP runner, exact cost handling, Performance Gate, regression tests, methodology and UAT are staged. No real Ask Brain benchmark report has run and underlying search/AI acceptance remains open. The story remains BLOCKED; no latency/throughput/cost performance claim is made.

S-10.06.01 is engineering-DONE. Release Gate `35789299001` passed the full backend suite, production frontend build/source contracts, repository verifier, PostgreSQL upgrade/downgrade/forward recovery, backup/restore and production readiness smoke on code commit `10a9028685f67ec6db923d3371a67df13276d044`. Official WorkOS activation and authenticated multi-user/revocation/accessibility browser UAT remain `UAT_PENDING`.

S-10.06.02 is engineering-DONE. Release Gate `35789299001` passed the full backend suite, production frontend build/source contracts, repository verifier and live PostgreSQL upgrade/downgrade/forward recovery across migrations `20260916_0022`/`0023`/`0024` on code commit `10a9028685f67ec6db923d3371a67df13276d044`. The executed backend suite includes participant/privacy/visibility-epoch regressions and `test_workspace_search_never_indexes_direct_message_body`. Authenticated WorkOS multi-user/privacy UAT remains `UAT_PENDING`.

S-10.07.01 intentionally has no EVIDENCE block yet. Governed project/channel-scoped agent runs, requester-only read model, current-context revalidation, approval boundaries, project-scoped tool execution, ephemeral final output and permission-refiltered artifacts are implementation-staged with frontend/BFF/UAT contracts. No current executable PASS or authenticated browser/provider/tool-safety UAT is claimed, so the story remains `IN_REVIEW`.

S-10.08.01 intentionally has no EVIDENCE block yet. Owner/Admin Admin Center aggregation plus membership/integration lifecycle, AI provider/model bootstrap, shared bounded AI credential validation and in-place credential rotation, API service/grant bootstrap, API grant owner/scope/environment/status/credential/revocation lifecycle, last-Owner/dormant-access cleanup protections, transient secret-entry UI, same-origin WorkOS BFF contracts, backend/frontend tests and UAT are staged. Current Ruff/Pytest/frontend build/source-contract execution, PostgreSQL-backed mutations, real secret-store smoke and authenticated browser/network UAT have not executed; GitHub-hosted jobs still fail before any step runs. The story remains `IN_REVIEW` and has no PASS/DONE evidence.


S-10.10.01 intentionally has no EVIDENCE block yet. The branch stages an opaque structural live revision over already-authorised Activity/channel/unread/selected-message/DM state, a same-origin WorkOS live BFF, adaptive visible/hidden/offline polling with bounded exponential backoff, selected-channel reaction/reply invalidation and an open-thread same-origin refresh loop. No WebSocket/SSE/broker/event-store dependency was added. Executable frontend/verifier evidence and official WorkOS two-user timing/revocation/offline browser UAT have not run, so the story remains `IN_REVIEW`.


S-10.11.01 intentionally has no EVIDENCE block yet. The branch stages a keyboard-first local quick switcher over already-authorised channels/projects/tracks/DM counterparts, a membership-validated same-origin BFF over the existing S-05.01 keyword Search API, bounded remote excerpts, exact permission-aware Brain-native message deep links, and explicit DM-content exclusion regressions. No second search index/provider was added. Executable backend/frontend/verifier evidence plus official WorkOS keyboard/revocation/private-source browser UAT remain outstanding, so the story remains `IN_REVIEW`.


S-10.12.01 intentionally has no EVIDENCE block yet. Repository implementation is staged for original-author-only edit/retract, expected-revision conflict protection, append-only revision snapshots linked to prior RawEvent/CanonicalEvent evidence, new immutable canonical lifecycle revisions, Search version retirement, mention/Activity/unread consistency, preserved thread tombstones, restricted-channel historical evidence grant cleanup, derived-content retention/legal-hold coverage, same-origin WorkOS BFF/UI and live invalidation. The latest Backend CI, Delivery Verifier and Release Gate jobs again ended before any job steps executed, and local checkout was unavailable because this execution environment could not resolve github.com. Therefore executable migration/backend/frontend/verifier evidence and authenticated WorkOS UAT remain outstanding; the story is IN_REVIEW, not DONE.


S-10.13.01 intentionally has no EVIDENCE block yet. Repository implementation is staged for bounded governed document/transcript upload, organisation/restricted native-channel evidence scope, live restricted membership checks, Work Graph/Search grant propagation, organisation-scoped database foreign keys, max-five message relations, file-only messages, safe attachment metadata, independent message/evidence lifecycle, attachment availability in live invalidation, same-origin WorkOS multipart upload, payload-bound message retry idempotency, channel/thread race guards, backend regressions and frontend source contracts. No executable PostgreSQL/backend/frontend/verifier PASS or authenticated WorkOS browser UAT is claimed, so the story remains IN_REVIEW.


S-10.14.01 intentionally has no EVIDENCE block yet. Repository implementation is staged for one short-lived organisation/user presence lease, one exact channel-or-DM typing lease, 75-second online expiry, 8-second typing expiry, write-side stale-row cleanup, read-only polling, current restricted-channel and participant-only DM permission filtering, no Owner/Admin DM override, no durable last-seen/draft/keystroke/IP/user-agent fields, no normal SecurityAuditEvent trail, bounded same-origin WorkOS routes, visible-tab heartbeat, throttled focused/non-empty composer typing, accessibility status text, migration `20260919_0031`, backend privacy/expiry/concurrency regressions and frontend source contracts. No executable PostgreSQL/backend/frontend/verifier PASS or authenticated WorkOS timing/privacy UAT is claimed, so the story remains IN_REVIEW.


S-10.15.01 intentionally has no EVIDENCE block yet. Repository implementation is staged for reference-only organisation/channel/message pin persistence, unique/idempotent channel-message pins, newest-pin-first ordering, current reader/writer permission rechecks, restricted-channel revocation safety, cross-channel/tenant fail-closed mutation, thread-reply pins, agent-message pin compatibility without changing agent edit authority, edit-preserved pins, same-transaction retraction cleanup, typed API/BFF, server-rendered accessible Pins panel, exact existing message/thread reopening, structural S-10.10 pin invalidation, migration `20260919_0032`, focused backend regressions and frontend source contracts. No executable PostgreSQL/backend/frontend/verifier PASS or authenticated WorkOS multi-user UAT is claimed, so the story remains IN_REVIEW.


S-10.16.01 intentionally has no EVIDENCE block yet. Repository implementation is staged for private reference-only organisation/user/message saves, membership/message scoped foreign keys, retry-safe uniqueness, newest-save-first ordering, current visible-channel filtering, restricted-channel revoke-hide/regrant-restore semantics, cross-user isolation with no privileged-role override, read-only-member Save support, agent-message Save compatibility without changing edit authority, edit-preserved saves, same-transaction retraction cleanup, audit-free Saved list/save/unsave traffic, typed API/BFF, server-rendered Saved navigation, exact existing root/thread deep links, migration `20260919_0033`, focused backend regressions and frontend source contracts. No executable PostgreSQL/backend/frontend/verifier PASS or authenticated WorkOS multi-user UAT is claimed, so the story remains IN_REVIEW.

S-10.17.01 intentionally has no EVIDENCE block yet. Repository implementation is staged for a set-based first-unread ID derived from the existing monotonic read cursor, own/retracted-message exclusion, exact permission-aware root/reply recovery, same-origin WorkOS GET, stable open-channel divider state across mark-read refresh, accessible Jump to unread, old-window/thread recovery, retracted-root reply compatibility, backend regressions, frontend/source contracts and authenticated UAT. No executable backend/frontend/verifier PASS or authenticated WorkOS multi-user UAT is claimed yet, so the story remains IN_REVIEW.

S-10.18.01 intentionally has no EVIDENCE block yet. Repository implementation is staged for participant-specific monotonic read cursors on the existing 1:1 DM aggregate, visibility-epoch reset, set-based unread/latest/first-unread summaries, own-message exclusion, exact participant-only message recovery, same-origin WorkOS read mutation, DM-list badges, stable accessible first-unread divider/jump UX, migration `20260919_0034`, backend epoch/revocation tests and frontend/security contracts. No executable PostgreSQL/backend/frontend/verifier PASS or authenticated WorkOS UAT is claimed yet, so the story remains IN_REVIEW.

S-10.19.01 intentionally has no EVIDENCE block yet. Repository implementation is staged for positive bounded `before_sequence` cursors on native channel roots and participant-visible DM messages, chronological page return, no OFFSET scans, current authorization/DM visibility-floor rechecks, same-origin WorkOS GET handling, merge-by-ID client history state, accessible Load older controls, backend cursor regressions and frontend/security contracts. No executable backend/frontend/verifier PASS or authenticated long-history/revocation UAT is claimed, so the story remains IN_REVIEW.

S-10.20.01 intentionally has no EVIDENCE block yet. Repository implementation is staged for original-author/current-epoch DM edit/retract, expected-revision conflict protection, private append-only revision snapshots, participant-safe body-free tombstones, retracted-message unread exclusion, no organisation-wide RawEvent/CanonicalEvent/Search/Work Graph/SecurityAuditEvent lifecycle projection, private-retention cascade, same-origin WorkOS PATCH/DELETE UI, migration `20260919_0035`, backend privacy/concurrency/retention regressions and frontend/security contracts. No executable PostgreSQL/backend/frontend/verifier PASS or authenticated WorkOS lifecycle UAT is claimed, so the story remains IN_REVIEW.

S-10.21.01 intentionally has no EVIDENCE block yet. Repository implementation is staged for root-scoped positive `before_sequence` reply pagination, chronological bounded pages, no OFFSET scans, same-origin WorkOS GET, merge-by-ID/sequence older-history state and additive live refresh. No executable backend/frontend/verifier PASS or authenticated long-thread UAT is claimed, so the story remains IN_REVIEW.

S-10.22.01 intentionally has no EVIDENCE block yet. Repository implementation is staged for tenant/root/user-scoped thread read state, set-based personal unread/latest/first-unread summaries, own/retracted reply exclusion, monotonic cross-root-safe mark-read, same-origin WorkOS mutation, root unread labels and stable New replies/Jump to unread UI, migration `20260920_0036`, backend regressions and frontend/security contracts. No executable PostgreSQL/backend/frontend/verifier PASS or authenticated WorkOS UAT is claimed, so the story remains IN_REVIEW.

S-10.23.01 intentionally has no EVIDENCE block yet. Repository implementation is staged for participant/current-epoch private reaction mutations, five-value allowlist, idempotent race recovery, batched aggregate count/reacted-by-me reads with no participant list, retraction/retention cascade, no organisation-wide evidence/search/audit projection, same-origin WorkOS PUT/DELETE UI, migration `20260920_0037`, backend privacy regressions and frontend/security contracts. No executable PostgreSQL/backend/frontend/verifier PASS or authenticated WorkOS UAT is claimed, so the story remains IN_REVIEW.

S-10.24.01 is engineering-DONE. Release Gate `35786803759` passed the backend suite, frontend production build/source contracts, repository verifier, PostgreSQL migration round-trip, backup/restore and production readiness smoke on code commit `ed0c701685ad01bd12a58389d9ec351d44d6d2fc`. OQ-009/OQ-010 continue to prevent implicit channel permission inheritance or shared DM grouping. Authenticated WorkOS UAT remains `UAT_PENDING`.

S-10.25.01 is engineering-DONE. Release Gate `35786803759` passed ACL-neutral Team/group navigation, audit rollback, frontend hierarchy contracts, repository verification and the PostgreSQL migration/recovery path on code commit `ed0c701685ad01bd12a58389d9ec351d44d6d2fc`. Authenticated WorkOS hierarchy/ACL UAT remains `UAT_PENDING`.

S-10.26.01 is engineering-DONE. Release Gate `35786803759` passed optimistic channel settings, archive/restore, restricted-member read/write propagation, audit rollback, frontend/security contracts, repository verification and PostgreSQL migration/recovery on code commit `ed0c701685ad01bd12a58389d9ec351d44d6d2fc`. Authenticated WorkOS channel-administration UAT remains `UAT_PENDING`.

EVIDENCE S-05.01.01
tests: backend/tests/test_search.py
command: cd backend && pytest
result: 384 passed, 2 warnings in 34.25s; Ruff passed (fresh Backend CI rerun in this session)
code: backend/app/search.py:342-635
commit: af9358c5f6d20079160c7fa77c4d771772d54703

EVIDENCE S-06.01.01
tests: backend/tests/test_ai_gateway.py
command: cd backend && pytest
result: 384 passed, 2 warnings in 34.25s; Ruff passed (fresh Backend CI rerun in this session)
code: backend/app/ai_provider_registry.py:323-518
commit: af9358c5f6d20079160c7fa77c4d771772d54703

EVIDENCE S-09.02.01
tests: backend/tests/test_data_governance.py
command: cd backend && pytest
result: 384 passed, 2 warnings in 34.25s; Ruff passed; Release Gate PostgreSQL migration/rollback/forward-recovery and backup/restore passed
code: backend/app/data_governance.py:126-1050
commit: af9358c5f6d20079160c7fa77c4d771772d54703



EVIDENCE S-10.24.01
tests: backend/tests/test_native_workspace.py::test_team_lifecycle_is_tenant_scoped_revisioned_and_manager_only
command: cd backend && pytest -q tests/test_native_workspace.py::test_team_lifecycle_is_tenant_scoped_revisioned_and_manager_only
result: passed in Release Gate 35786803759; full backend suite 385 passed, 2 warnings in 34.45s; frontend build/contracts 138 passed, 0 failed
code: backend/app/native_workspace.py:108-261
commit: ed0c701685ad01bd12a58389d9ec351d44d6d2fc

EVIDENCE S-10.25.01
tests: backend/tests/test_native_workspace.py::test_channel_group_and_navigation_roll_back_when_audit_persistence_fails
command: cd backend && pytest -q tests/test_native_workspace.py::test_channel_group_and_navigation_roll_back_when_audit_persistence_fails
result: passed in Release Gate 35786803759; full backend suite 385 passed, 2 warnings in 34.45s; frontend build/contracts 138 passed, 0 failed
code: backend/app/native_workspace.py:262-570
commit: ed0c701685ad01bd12a58389d9ec351d44d6d2fc

EVIDENCE S-10.26.01
tests: backend/tests/test_native_workspace.py::test_channel_administration_is_revisioned_read_only_when_archived_and_syncs_track
command: cd backend && pytest -q tests/test_native_workspace.py::test_channel_administration_is_revisioned_read_only_when_archived_and_syncs_track
result: passed in Release Gate 35786803759; full backend suite 385 passed, 2 warnings in 34.45s; frontend build/contracts 138 passed, 0 failed
code: backend/app/native_chat.py:516-763
commit: ed0c701685ad01bd12a58389d9ec351d44d6d2fc

EVIDENCE S-10.01.01
tests: backend/tests/test_native_chat.py
command: cd backend && pytest -q tests/test_native_chat.py
result: Release Gate 35789299001 passed; backend 385 passed, 2 warnings; frontend production build completed and source-contract tests 138 passed, 0 failed; PostgreSQL upgrade/downgrade/forward recovery passed
code: backend/app/native_chat.py:172-1483
commit: 10a9028685f67ec6db923d3371a67df13276d044

EVIDENCE S-10.06.01
tests: backend/tests/test_native_conversation.py
command: cd backend && pytest -q tests/test_native_conversation.py
result: Release Gate 35789299001 passed; backend 385 passed, 2 warnings; frontend production build completed and source-contract tests 138 passed, 0 failed; Delivery Verifier and PostgreSQL migration recovery passed
code: backend/app/native_conversation.py:505-1345
commit: 10a9028685f67ec6db923d3371a67df13276d044

EVIDENCE S-10.06.02
tests: backend/tests/test_direct_messages.py
command: cd backend && pytest -q tests/test_direct_messages.py
result: Release Gate 35789299001 passed; backend 385 passed, 2 warnings; frontend production build completed and source-contract tests 138 passed, 0 failed; PostgreSQL migrations 0022/0023/0024 participated in successful downgrade/forward-recovery
code: backend/app/direct_messages.py:238-953
commit: 10a9028685f67ec6db923d3371a67df13276d044

