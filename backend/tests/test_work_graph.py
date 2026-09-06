from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CanonicalEvent,
    IntegrationConnection,
    Membership,
    MembershipRole,
    Organization,
    RawEvent,
    ResourceAccessLevel,
    ResourceGrant,
    SlackChannelAuthorization,
    SourceIdentity,
    SourceIdentityState,
    User,
)
from app.work_graph import (
    WorkGraphError,
    create_manual_edge,
    create_manual_node,
    project_canonical_event,
    traverse_work_graph,
)
from app.work_graph_models import (
    WorkGraphEdge,
    WorkGraphEdgeSource,
    WorkGraphEdgeType,
    WorkGraphEvidenceState,
    WorkGraphNode,
    WorkGraphNodeType,
)


def _seed_org(db: Session, suffix: str):
    owner = User(email=f"owner-{suffix}@example.com", display_name=f"Owner {suffix}")
    member = User(email=f"member-{suffix}@example.com", display_name=f"Member {suffix}")
    organization = Organization(name=f"Org {suffix}", slug=f"org-{suffix}")
    db.add_all([owner, member, organization])
    db.flush()
    db.add_all(
        [
            Membership(
                organization_id=organization.id,
                user_id=owner.id,
                role=MembershipRole.OWNER,
            ),
            Membership(
                organization_id=organization.id,
                user_id=member.id,
                role=MembershipRole.MEMBER,
            ),
        ]
    )
    db.commit()
    return organization, owner, member


def _canonical_event(
    db: Session,
    *,
    organization: Organization,
    owner: User,
    provider: str,
    visibility: str,
    source_acl: list[str],
    object_type: str,
    object_external_id: str,
    metadata: dict[str, object],
) -> CanonicalEvent:
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider=provider,
        external_account_id=f"{provider}-{organization.slug}",
        display_name=f"{provider} connection",
        scopes=[],
        provider_metadata={},
        created_by_user_id=owner.id,
    )
    db.add(connection)
    db.flush()
    raw = RawEvent(
        organization_id=organization.id,
        integration_connection_id=connection.id,
        provider=provider,
        source_event_id=f"event-{provider}-{object_external_id}",
        source_event_type="message" if provider == "slack" else "pull_request",
        delivery_kind="webhook",
        source_timestamp=datetime.now(UTC),
        content_type="application/json",
        payload_sha256="a" * 64,
        raw_payload=b"{}",
        source_visibility=visibility,
        source_acl=source_acl,
    )
    db.add(raw)
    db.flush()
    identity = SourceIdentity(
        organization_id=organization.id,
        provider=provider,
        external_id=f"actor-{provider}-{organization.slug}",
        display_name="Source Actor",
        email=None,
        email_verified=False,
        state=SourceIdentityState.RESOLVED,
        resolved_user_id=owner.id,
        resolution_method="manual",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    db.add(identity)
    db.flush()
    event = CanonicalEvent(
        organization_id=organization.id,
        raw_event_id=raw.id,
        integration_connection_id=connection.id,
        source_identity_id=identity.id,
        resolved_user_id=owner.id,
        schema_version=1,
        event_type="message.created" if provider == "slack" else "pull_request.opened",
        action="created" if provider == "slack" else "opened",
        actor_type=f"{provider}_user",
        actor_external_id=identity.external_id,
        actor_display_name=identity.display_name,
        object_type=object_type,
        object_external_id=object_external_id,
        object_display_name=f"Object {object_external_id}",
        source_provider=provider,
        source_event_id=raw.source_event_id,
        source_event_type=raw.source_event_type,
        occurred_at=datetime.now(UTC),
        source_visibility=visibility,
        source_acl=source_acl,
        provenance={"raw_event_id": str(raw.id)},
        event_metadata=metadata,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def test_slack_projection_is_typed_and_idempotent(db_session: Session) -> None:
    organization, owner, _ = _seed_org(db_session, "slack-graph")
    event = _canonical_event(
        db_session,
        organization=organization,
        owner=owner,
        provider="slack",
        visibility="public_channel",
        source_acl=[],
        object_type="message",
        object_external_id="C1:100.0",
        metadata={"channel_id": "C1"},
    )

    first = project_canonical_event(db_session, event)
    second = project_canonical_event(db_session, event)

    assert first.id == second.id
    nodes = list(db_session.scalars(select(WorkGraphNode)))
    edges = list(db_session.scalars(select(WorkGraphEdge)))
    assert {node.node_type for node in nodes} == {
        WorkGraphNodeType.PERSON,
        WorkGraphNodeType.TRACK,
        WorkGraphNodeType.EVIDENCE,
    }
    assert len(nodes) == 4
    assert {edge.edge_type for edge in edges} == {
        WorkGraphEdgeType.PERFORMED,
        WorkGraphEdgeType.RESOLVES_TO,
        WorkGraphEdgeType.SUPPORTED_BY,
    }
    assert len(edges) == 3
    assert all(edge.evidence_state == WorkGraphEvidenceState.VERIFIED for edge in edges)


def test_private_slack_graph_uses_current_membership_not_historical_acl(
    db_session: Session,
) -> None:
    organization, owner, member = _seed_org(db_session, "slack-private")
    member_slack_id = "U-MEMBER"
    event = _canonical_event(
        db_session,
        organization=organization,
        owner=owner,
        provider="slack",
        visibility="private_channel",
        source_acl=[member_slack_id],
        object_type="message",
        object_external_id="C-private:100.0",
        metadata={"channel_id": "C-private"},
    )
    db_session.add(
        SourceIdentity(
            organization_id=organization.id,
            provider="slack",
            external_id=member_slack_id,
            display_name="Private Member",
            email=None,
            email_verified=False,
            state=SourceIdentityState.RESOLVED,
            resolved_user_id=member.id,
            resolution_method="manual",
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
        )
    )
    authorization = SlackChannelAuthorization(
        organization_id=organization.id,
        integration_connection_id=event.integration_connection_id,
        channel_id="C-private",
        channel_name="private",
        is_private=True,
        member_ids=[member_slack_id],
        authorized_by_user_id=owner.id,
    )
    db_session.add(authorization)
    db_session.commit()

    project_canonical_event(db_session, event)
    track = db_session.scalar(
        select(WorkGraphNode).where(WorkGraphNode.node_type == WorkGraphNodeType.TRACK)
    )
    assert track is not None
    allowed = traverse_work_graph(
        db_session,
        organization_id=organization.id,
        start_node_id=track.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        depth=1,
    )
    assert allowed is not None

    authorization.member_ids = []
    db_session.commit()

    denied = traverse_work_graph(
        db_session,
        organization_id=organization.id,
        start_node_id=track.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        depth=1,
    )
    assert denied is None
    assert member_slack_id in track.source_acl


def test_private_github_graph_fails_closed_until_explicit_grant(db_session: Session) -> None:
    organization, owner, member = _seed_org(db_session, "github-private")
    event = _canonical_event(
        db_session,
        organization=organization,
        owner=owner,
        provider="github",
        visibility="private_repository",
        source_acl=["github:repository:42"],
        object_type="pull_request",
        object_external_id="99",
        metadata={"repository_id": "42", "repository": "acme/private"},
    )
    project_canonical_event(db_session, event)
    project = db_session.scalar(
        select(WorkGraphNode).where(WorkGraphNode.node_type == WorkGraphNodeType.PROJECT)
    )
    assert project is not None

    denied = traverse_work_graph(
        db_session,
        organization_id=organization.id,
        start_node_id=project.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        depth=2,
    )
    assert denied is None

    db_session.add(
        ResourceGrant(
            organization_id=organization.id,
            resource_type="github.repository",
            resource_id="42",
            user_id=member.id,
            access=ResourceAccessLevel.READ,
            created_by_user_id=owner.id,
        )
    )
    db_session.commit()
    allowed = traverse_work_graph(
        db_session,
        organization_id=organization.id,
        start_node_id=project.id,
        user_id=member.id,
        role=MembershipRole.MEMBER,
        depth=2,
    )
    assert allowed is not None
    nodes, edges = allowed
    assert any(node.node_type == WorkGraphNodeType.WORK_ITEM for node in nodes)
    assert any(node.node_type == WorkGraphNodeType.EVIDENCE for node in nodes)
    assert edges


def test_cross_tenant_manual_edge_is_rejected(db_session: Session) -> None:
    org_one, owner_one, _ = _seed_org(db_session, "graph-one")
    org_two, owner_two, _ = _seed_org(db_session, "graph-two")
    project = create_manual_node(
        db_session,
        organization_id=org_one.id,
        node_type=WorkGraphNodeType.PROJECT,
        key="atlas",
        display_name="Atlas",
        actor_user_id=owner_one.id,
    )
    track = create_manual_node(
        db_session,
        organization_id=org_two.id,
        node_type=WorkGraphNodeType.TRACK,
        key="backend",
        display_name="Backend",
        actor_user_id=owner_two.id,
    )

    with pytest.raises(WorkGraphError, match="Both graph nodes"):
        create_manual_edge(
            db_session,
            organization_id=org_one.id,
            source_node_id=project.id,
            target_node_id=track.id,
            edge_type=WorkGraphEdgeType.CONTAINS,
            actor_user_id=owner_one.id,
            reason="Wrong tenant",
        )


def test_inferred_edges_are_explicitly_distinguishable(db_session: Session) -> None:
    organization, owner, _ = _seed_org(db_session, "graph-inferred")
    project = create_manual_node(
        db_session,
        organization_id=organization.id,
        node_type=WorkGraphNodeType.PROJECT,
        key="atlas",
        display_name="Atlas",
        actor_user_id=owner.id,
    )
    track = create_manual_node(
        db_session,
        organization_id=organization.id,
        node_type=WorkGraphNodeType.TRACK,
        key="backend",
        display_name="Backend",
        actor_user_id=owner.id,
    )
    edge = WorkGraphEdge(
        organization_id=organization.id,
        source_node_id=project.id,
        target_node_id=track.id,
        edge_type=WorkGraphEdgeType.RELATED_TO,
        source_kind=WorkGraphEdgeSource.INFERENCE,
        evidence_state=WorkGraphEvidenceState.INFERRED,
        confidence=0.62,
        provenance_key="inference:test:atlas-backend",
        provenance={"method": "evaluation_fixture"},
    )
    db_session.add(edge)
    db_session.commit()

    stored = db_session.scalar(select(WorkGraphEdge).where(WorkGraphEdge.id == edge.id))
    assert stored is not None
    assert stored.source_kind == WorkGraphEdgeSource.INFERENCE
    assert stored.evidence_state == WorkGraphEvidenceState.INFERRED
    assert stored.confidence == pytest.approx(0.62)
