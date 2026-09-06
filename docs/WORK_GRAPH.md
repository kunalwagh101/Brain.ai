# Work Graph

The Work Graph is Brain's tenant-scoped relationship projection over canonical evidence. It does not replace raw or canonical evidence and it is not an independent source of truth.

## Storage

Increment 7 uses PostgreSQL relationship tables only:

- `work_graph_nodes`
- `work_graph_edges`

No graph database dependency is introduced. Nodes keep stable references and minimal metadata; message/code content remains in the canonical/raw evidence stores.

Node types are `person`, `project`, `track`, `work_item`, and `evidence`.

Edges carry:

- relation type
- source kind
- evidence state (`VERIFIED` or `INFERRED`)
- confidence
- provenance key and provenance payload
- optional canonical-event reference

`VERIFIED` is reserved for deterministic source rules or explicit authorised manual assertions. Inference is stored as `INFERRED`; model output must never silently create a verified relationship.

## Projection rules

Canonical Slack/GitHub events are projected after canonicalisation.

- A canonical event creates/reuses one evidence node by canonical-event ID.
- Slack channel evidence creates/reuses a track node scoped to the integration connection and channel.
- GitHub repository evidence creates/reuses a project node scoped to the integration connection and repository.
- Non-repository GitHub objects create/reuse work-item nodes under the repository project.
- Source identities create distinct person nodes.
- Brain users create distinct person nodes.
- Current identity resolution is represented by a reversible `resolves_to` edge.
- Canonical actor activity may create a verified `performed` edge to evidence.

Projection and reconciliation are idempotent. Reconciliation is limit-bounded and queries only canonical events that have not yet been projected.

## Manual mutations

The API allows authorised users with `resource.write` to create manual `project`, `track`, and `work_item` nodes.

Manual edges are limited to safe organisational relationships such as `contains`, `depends_on`, and `related_to`. Manual mutations cannot assert person identity relationships. Cross-tenant edges are rejected.

## Traversal and permissions

Graph traversal is tenant-filtered and bounded to depth 0-3.

Public/organisation-visible nodes may be returned to an authorised organisation reader. Restricted nodes fail closed unless the caller has the same kind of explicit source/resource access used elsewhere in Brain.

Private Slack authorization is evaluated from the current `SlackChannelAuthorization.member_ids`, not historical event ACL snapshots. Historical ACL values remain provenance only. A user removed from a private channel therefore loses graph traversal even though older canonical events still record prior membership.

Private GitHub evidence requires an explicit repository or graph-node resource grant. Owner/Admin status does not bypass the existing restricted-resource ACL contract.

The graph must never become a second, broader permission system. F-05.01 will provide the complete permission-aware retrieval layer used by search/Ask Brain.

## API

Base path: `/api/v1/organizations/{organization_id}/work-graph`

- `POST /nodes` create an allowed manual node
- `POST /edges` create an allowed manual edge
- `GET /nodes/{node_id}/neighbors?depth=1` traverse a visible subgraph
- `POST /reconcile?limit=100` project existing unprojected canonical events

## Migration and recovery

Schema revision: `20260906_0008`, revising `20260906_0007`.

Before rollback:

1. stop canonicalisation paths that project new graph evidence;
2. stop work-graph reconciliation and graph API mutations;
3. export graph rows only if needed for investigation/debugging.

Downgrading `20260906_0008` removes Work Graph nodes/edges. It does not remove canonical events, raw events, source identities, or identity-resolution history. The graph can therefore be rebuilt deterministically from retained evidence after the schema is reintroduced.

## Verification

Primary automated suite: `backend/tests/test_work_graph.py`.

The suite covers typed/idempotent projection, restricted GitHub fail-closed behavior, current private-Slack membership revocation, cross-tenant rejection, explicit inferred-state handling, and reversible identity-resolution graph links.

Real provider data and frontend/manual acceptance remain separate under `UAT/F-04.01.md`.