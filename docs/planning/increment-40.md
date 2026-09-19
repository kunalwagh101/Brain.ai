# Increment 40 — Workspace Teams

Story: `S-10.24.01`

Status: `IN_REVIEW`

## Sprint goal

Replace the flat-only workspace structure with real shared Team containers while preserving every existing channel/DM permission boundary.

## Vertical slice

Create/list/edit/archive/restore Teams through FastAPI and same-origin WorkOS. Render active Teams in the workspace navigation plus an explicit **Unassigned channels** fallback. Team metadata never contains message/DM/evidence content and never grants access.

## Security boundary

OQ-009: Teams are navigation metadata only; restricted-channel ACLs remain explicit.  
OQ-010: participant-private DMs stay in their personal section.

## Reuse

Existing organisation membership, native-chat write role gate, creator-or-Owner/Admin manager pattern, bounded JSON route helpers, audit events and workspace shell.

## Acceptance truth

Repository implementation may reach `IN_REVIEW`; executable migration/tests/verifier and authenticated UAT remain required for DONE.

## Retrospective — 2026-09-20

No accepted requirement was cut. The key design choice was keeping Team hierarchy out of the authorization model. This preserves the already-tested restricted-channel/evidence permission boundary while still delivering the missing Slack/Discord company structure. The migration is isolated and reversible; existing channels remain visible under Unassigned channels. Two product/security ambiguities were surfaced as OQ-009/OQ-010 rather than guessed. The story remains IN_REVIEW pending executable migration/tests/verifier and authenticated UAT.
