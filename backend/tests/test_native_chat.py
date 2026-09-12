import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.main import app
from app.models import (
    CanonicalEvent,
    Membership,
    MembershipRole,
    Organization,
    RawEvent,
    ResourceAccessLevel,
    User,
)
from app.native_chat_models import (
    NativeChannel,
    NativeMessage,
    NativeMessageActorKind,
    NativeMessageProjectionStatus,
)
from app.search import SearchMode, search_documents
from app.search_models import SearchDocument
from app.work_graph_models import WorkGraphNode, WorkGraphNodeType


def _seed(db: Session, suffix: str):
    owner = User(
        email=f"native-owner-{suffix}@example.com",
        display_name="Owner User",
    )
    executive = User(
        email=f"native-executive-{suffix}@example.com",
        display_name="Executive User",
    )
    member = User(
        email=f"native-member-{suffix}@example.com",
        display_name="Member User",
    )
    other = User(
        email=f"native-other-{suffix}@example.com",
        display_name="Other Member",
    )
    guest = User(
        email=f"native-guest-{suffix}@example.com",
        display_name="Guest User",
    )
    organization = Organization(
        name=f"Native Chat {suffix}",
        slug=f"native-chat-{suffix}",
    )
    db.add_all([owner, executive, member, other, guest, organization])
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
                user_id=executive.id,
                role=MembershipRole.EXECUTIVE,
            ),
            Membership(
                organization_id=organization.id,
                user_id=member.id,
                role=MembershipRole.MEMBER,
            ),
            Membership(
                organization_id=organization.id,
                user_id=other.id,
                role=MembershipRole.MEMBER,
            ),
            Membership(
                organization_id=organization.id,
                user_id=guest.id,
                role=MembershipRole.GUEST,
            ),
        ]
    )
    db.commit()
    return organization, owner, executive, member, other, guest


def _as(user):
    app.dependency_overrides[get_current_user] = lambda: user


def _create_channel(client, organization, user, *, name: str, visibility: str):
    _as(user)
    return client.post(
        f"/api/v1/organizations/{organization.id}/native-channels",
        json={
            "name": name,
            "description": f"{name} collaboration",
            "visibility": visibility,
        },
    )


def _send(client, organization, channel_id, user, body, key):
    _as(user)
    return client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel_id}/messages",
        headers={"Idempotency-Key": key},
        json={"body": body},
    )


def test_public_channel_exec_can_write_guest_can_only_read(
    db_session: Session,
    client,
) -> None:
    organization, _, executive, _, _, guest = _seed(db_session, "roles")

    created = _create_channel(
        client,
        organization,
        executive,
        name="Leadership",
        visibility="organization",
    )
    assert created.status_code == 201
    channel_id = created.json()["id"]
    assert created.json()["can_post"] is True

    sent = _send(
        client,
        organization,
        channel_id,
        executive,
        "Decision: launch the guarded beta on Monday.",
        "exec-message-1",
    )
    assert sent.status_code == 201
    assert sent.json()["actor_kind"] == "user"
    assert sent.json()["projection_status"] == "ready"

    _as(guest)
    listed = client.get(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel_id}/messages"
    )
    denied = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel_id}/messages",
        json={"body": "Guest write attempt"},
    )
    assert listed.status_code == 200
    assert [row["body"] for row in listed.json()] == [
        "Decision: launch the guarded beta on Monday."
    ]
    assert denied.status_code == 403


def test_message_projects_to_canonical_work_graph_and_search(
    db_session: Session,
    client,
) -> None:
    organization, owner, _, _, _, _ = _seed(db_session, "projection")
    created = _create_channel(
        client,
        organization,
        owner,
        name="Platform",
        visibility="organization",
    )
    assert created.status_code == 201
    channel_id = created.json()["id"]

    sent = _send(
        client,
        organization,
        channel_id,
        owner,
        "Blocker: the production database migration requires review.",
        "projection-message",
    )
    assert sent.status_code == 201
    message_id = sent.json()["id"]

    message = db_session.get(NativeMessage, message_id)
    assert message is not None
    assert message.actor_kind == NativeMessageActorKind.USER
    assert message.projection_status == NativeMessageProjectionStatus.READY
    assert message.raw_event_id is not None
    assert message.canonical_event_id is not None

    raw = db_session.get(RawEvent, message.raw_event_id)
    canonical = db_session.get(CanonicalEvent, message.canonical_event_id)
    assert raw is not None
    assert canonical is not None
    assert raw.provider == "brain_native"
    assert canonical.source_provider == "brain_native"
    assert canonical.event_metadata["channel_id"] == channel_id
    assert canonical.event_metadata["text"].startswith("Blocker:")

    evidence = db_session.scalar(
        select(WorkGraphNode).where(
            WorkGraphNode.canonical_event_id == canonical.id,
            WorkGraphNode.node_type == WorkGraphNodeType.EVIDENCE,
        )
    )
    document = db_session.scalar(
        select(SearchDocument).where(SearchDocument.canonical_event_id == canonical.id)
    )
    assert evidence is not None
    assert document is not None
    assert document.content == "Blocker: the production database migration requires review."
    assert document.work_graph_node_id == evidence.id

    result = search_documents(
        db_session,
        organization_id=organization.id,
        user_id=owner.id,
        query="production database migration",
        mode=SearchMode.KEYWORD,
        limit=10,
        embedding_client=None,
        embedding_model=None,
    )
    assert any(hit.document.id == document.id for hit in result.hits)


def test_restricted_channel_membership_and_revocation_remove_future_access(
    db_session: Session,
    client,
) -> None:
    organization, owner, _, member, other, _ = _seed(db_session, "restricted")
    created = _create_channel(
        client,
        organization,
        owner,
        name="Acquisition",
        visibility="restricted",
    )
    assert created.status_code == 201
    channel_id = created.json()["id"]

    message = _send(
        client,
        organization,
        channel_id,
        owner,
        "Confidential launch plan for Project Atlas.",
        "restricted-message",
    )
    assert message.status_code == 201

    _as(member)
    hidden = client.get(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel_id}"
    )
    assert hidden.status_code == 404

    _as(owner)
    granted = client.put(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel_id}/members/{member.id}",
        json={"access": "read"},
    )
    assert granted.status_code == 200
    assert granted.json()["access"] == "read"

    _as(member)
    visible = client.get(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel_id}/messages"
    )
    cannot_post = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel_id}/messages",
        json={"body": "Read-only member cannot send"},
    )
    assert visible.status_code == 200
    assert visible.json()[0]["body"].startswith("Confidential")
    assert cannot_post.status_code == 404

    search_before = search_documents(
        db_session,
        organization_id=organization.id,
        user_id=member.id,
        query="Project Atlas",
        mode=SearchMode.KEYWORD,
        limit=10,
        embedding_client=None,
        embedding_model=None,
    )
    assert search_before.hits

    _as(owner)
    revoked = client.delete(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel_id}/members/{member.id}"
    )
    assert revoked.status_code == 204

    _as(member)
    after = client.get(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel_id}/messages"
    )
    assert after.status_code == 404
    search_after = search_documents(
        db_session,
        organization_id=organization.id,
        user_id=member.id,
        query="Project Atlas",
        mode=SearchMode.KEYWORD,
        limit=10,
        embedding_client=None,
        embedding_model=None,
    )
    assert search_after.hits == []

    _as(other)
    never_member = client.get(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel_id}"
    )
    assert never_member.status_code == 404

    canonical_count = len(
        list(
            db_session.scalars(
                select(CanonicalEvent).where(
                    CanonicalEvent.organization_id == organization.id,
                    CanonicalEvent.source_provider == "brain_native",
                )
            )
        )
    )
    assert canonical_count == 1


def test_message_idempotency_and_agent_spoofing_fail_closed(
    db_session: Session,
    client,
) -> None:
    organization, owner, _, _, _, _ = _seed(db_session, "idempotency")
    created = _create_channel(
        client,
        organization,
        owner,
        name="Engineering",
        visibility="organization",
    )
    channel_id = created.json()["id"]

    first = _send(
        client,
        organization,
        channel_id,
        owner,
        "Ship the reviewed patch.",
        "same-message-key",
    )
    second = _send(
        client,
        organization,
        channel_id,
        owner,
        "Ship the reviewed patch.",
        "same-message-key",
    )
    conflict = _send(
        client,
        organization,
        channel_id,
        owner,
        "Different content under the same key.",
        "same-message-key",
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert conflict.status_code == 409

    _as(owner)
    spoof = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel_id}/messages",
        json={
            "body": "Pretend an agent wrote this",
            "actor_kind": "agent",
            "agent_run_id": str(uuid.uuid4()),
        },
    )
    assert spoof.status_code == 422


def test_cross_tenant_channel_ids_do_not_leak(
    db_session: Session,
    client,
) -> None:
    organization_a, owner_a, _, _, _, _ = _seed(db_session, "tenant-a")
    _, owner_b, _, _, _, _ = _seed(db_session, "tenant-b")
    created = _create_channel(
        client,
        organization_a,
        owner_a,
        name="Tenant A",
        visibility="organization",
    )
    channel_id = created.json()["id"]

    _as(owner_b)
    read = client.get(
        f"/api/v1/organizations/{organization_a.id}/native-channels/{channel_id}"
    )
    messages = client.get(
        f"/api/v1/organizations/{organization_a.id}/native-channels/"
        f"{channel_id}/messages"
    )
    send = client.post(
        f"/api/v1/organizations/{organization_a.id}/native-channels/"
        f"{channel_id}/messages",
        json={"body": "Cross-tenant attempt"},
    )
    assert read.status_code == 404
    assert messages.status_code == 404
    assert send.status_code == 404
