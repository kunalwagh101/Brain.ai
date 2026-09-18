import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.activity import list_activity
from app.activity_models import ActivityKind
from app.auth import get_current_user
from app.data_governance import run_retention_once, set_retention_policy
from app.data_governance_models import SecurityAuditEvent
from app.main import app
from app.models import Membership, MembershipRole, Organization, User
from app.native_chat_models import (
    NativeMessage,
    NativeMessageRevision,
    NativeMessageRevisionAction,
)
from app.native_conversation_models import NativeMessageMention
from app.search_models import SearchDocument


def _as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _seed(db: Session, suffix: str):
    organization = Organization(
        name=f"Lifecycle {suffix}",
        slug=f"lifecycle-{suffix}-{uuid.uuid4().hex[:6]}",
    )
    author = User(
        email=f"author-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Author",
    )
    member = User(
        email=f"member-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Member",
    )
    other = User(
        email=f"other-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Other",
    )
    admin = User(
        email=f"admin-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Admin",
    )
    guest = User(
        email=f"guest-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Guest",
    )
    outsider_org = Organization(
        name=f"Other {suffix}",
        slug=f"other-{suffix}-{uuid.uuid4().hex[:6]}",
    )
    outsider = User(
        email=f"outsider-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Outsider",
    )
    db.add_all(
        [
            organization,
            outsider_org,
            author,
            member,
            other,
            admin,
            guest,
            outsider,
        ]
    )
    db.flush()
    db.add_all(
        [
            Membership(
                organization_id=organization.id,
                user_id=author.id,
                role=MembershipRole.MEMBER,
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
                user_id=admin.id,
                role=MembershipRole.ADMIN,
            ),
            Membership(
                organization_id=organization.id,
                user_id=guest.id,
                role=MembershipRole.GUEST,
            ),
            Membership(
                organization_id=outsider_org.id,
                user_id=outsider.id,
                role=MembershipRole.OWNER,
            ),
        ]
    )
    db.commit()
    return organization, author, member, other, admin, guest, outsider


def _channel(client, organization, actor, visibility="organization"):
    _as(actor)
    response = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels",
        json={
            "name": f"lifecycle-{uuid.uuid4().hex[:6]}",
            "visibility": visibility,
        },
    )
    assert response.status_code == 201
    return response.json()


def _message(client, organization, channel_id, actor, body, key):
    _as(actor)
    response = client.post(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel_id}/messages",
        headers={"Idempotency-Key": key},
        json={"body": body},
    )
    assert response.status_code == 201
    return response.json()


def _edit(client, organization, channel_id, message_id, actor, body, revision):
    _as(actor)
    return client.patch(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel_id}/messages/{message_id}",
        json={"body": body, "expected_revision": revision},
    )


def _retract(client, organization, channel_id, message_id, actor, revision):
    _as(actor)
    return client.request(
        "DELETE",
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel_id}/messages/{message_id}",
        json={"expected_revision": revision},
    )


def _search(client, organization, actor, query):
    _as(actor)
    return client.get(
        f"/api/v1/organizations/{organization.id}/search",
        params={"q": query, "mode": "keyword", "limit": 12},
    )


def test_author_edit_reconciles_search_mentions_history_and_audit(
    db_session: Session,
    client,
) -> None:
    organization, author, member, other, _, _, _ = _seed(db_session, "edit")
    channel = _channel(client, organization, author)
    old_sentinel = f"old-{uuid.uuid4().hex}"
    new_sentinel = f"new-{uuid.uuid4().hex}"
    created = _message(
        client,
        organization,
        channel["id"],
        author,
        f"{old_sentinel} please review @{member.email}",
        "lifecycle-edit",
    )
    assert created["revision"] == 1

    before_activity = list_activity(
        db_session,
        organization_id=organization.id,
        user_id=member.id,
        limit=20,
    )
    assert any(item.kind == ActivityKind.MENTION for item in before_activity)

    edited = _edit(
        client,
        organization,
        channel["id"],
        created["id"],
        author,
        f"{new_sentinel} please review @{other.email}",
        1,
    )
    assert edited.status_code == 200
    body = edited.json()
    assert body["revision"] == 2
    assert body["edited_at"] is not None
    assert body["deleted_at"] is None
    assert body["can_edit"] is True
    assert body["can_delete"] is True

    old_search = _search(client, organization, author, old_sentinel)
    new_search = _search(client, organization, author, new_sentinel)
    assert old_search.status_code == 200
    assert new_search.status_code == 200
    assert old_search.json()["results"] == []
    assert any(item["object_external_id"] == created["id"] for item in new_search.json()["results"])

    mention_rows = list(
        db_session.scalars(
            select(NativeMessageMention).where(
                NativeMessageMention.message_id == uuid.UUID(created["id"])
            )
        )
    )
    assert [row.mentioned_user_id for row in mention_rows] == [other.id]
    after_removed = list_activity(
        db_session,
        organization_id=organization.id,
        user_id=member.id,
        limit=20,
    )
    after_added = list_activity(
        db_session,
        organization_id=organization.id,
        user_id=other.id,
        limit=20,
    )
    assert all(item.kind != ActivityKind.MENTION for item in after_removed)
    assert any(item.kind == ActivityKind.MENTION for item in after_added)

    revisions = list(
        db_session.scalars(
            select(NativeMessageRevision).where(
                NativeMessageRevision.message_id == uuid.UUID(created["id"])
            )
        )
    )
    assert len(revisions) == 1
    assert revisions[0].revision == 1
    assert revisions[0].action == NativeMessageRevisionAction.EDIT
    assert old_sentinel in revisions[0].body

    audit = db_session.scalar(
        select(SecurityAuditEvent).where(
            SecurityAuditEvent.organization_id == organization.id,
            SecurityAuditEvent.event_type == "native_chat.message.edited",
        )
    )
    assert audit is not None
    audit_text = json.dumps(audit.metadata_json, sort_keys=True)
    assert old_sentinel not in audit_text
    assert new_sentinel not in audit_text
    assert audit.metadata_json["previous_revision"] == 1
    assert audit.metadata_json["current_revision"] == 2

    document = db_session.scalar(
        select(SearchDocument).where(
            SearchDocument.organization_id == organization.id,
            SearchDocument.object_external_id == created["id"],
        )
    )
    assert document is not None
    assert document.content.startswith(new_sentinel)
    assert document.provenance["native_message_revision"] == 2


def test_stale_revision_and_non_author_mutations_fail_closed(
    db_session: Session,
    client,
) -> None:
    organization, author, _, _, admin, guest, outsider = _seed(db_session, "authority")
    channel = _channel(client, organization, author)
    created = _message(
        client,
        organization,
        channel["id"],
        author,
        "Original author content.",
        "lifecycle-authority",
    )

    first = _edit(
        client,
        organization,
        channel["id"],
        created["id"],
        author,
        "First accepted edit.",
        1,
    )
    assert first.status_code == 200

    stale = _edit(
        client,
        organization,
        channel["id"],
        created["id"],
        author,
        "Stale overwrite attempt.",
        1,
    )
    assert stale.status_code == 409

    admin_attempt = _edit(
        client,
        organization,
        channel["id"],
        created["id"],
        admin,
        "Admin must not override author ownership.",
        2,
    )
    assert admin_attempt.status_code == 404

    guest_attempt = _retract(
        client,
        organization,
        channel["id"],
        created["id"],
        guest,
        2,
    )
    assert guest_attempt.status_code in {403, 404}

    outsider_attempt = _edit(
        client,
        organization,
        channel["id"],
        created["id"],
        outsider,
        "Cross-tenant attempt.",
        2,
    )
    assert outsider_attempt.status_code in {403, 404}

    persisted = db_session.get(NativeMessage, uuid.UUID(created["id"]))
    assert persisted is not None
    assert persisted.body == "First accepted edit."
    assert persisted.revision == 2


def test_revoked_author_can_no_longer_edit_or_retract(
    db_session: Session,
    client,
) -> None:
    organization, author, _, _, admin, _, _ = _seed(db_session, "revoked")
    channel = _channel(client, organization, admin, visibility="restricted")

    _as(admin)
    invited = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel['id']}/members",
        json={"email": author.email, "access": "write"},
    )
    assert invited.status_code == 201

    created = _message(
        client,
        organization,
        channel["id"],
        author,
        "Restricted author message.",
        "lifecycle-revoked",
    )

    _as(admin)
    revoked = client.delete(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel['id']}/members/{author.id}"
    )
    assert revoked.status_code == 204

    edit = _edit(
        client,
        organization,
        channel["id"],
        created["id"],
        author,
        "No longer allowed.",
        1,
    )
    retract = _retract(
        client,
        organization,
        channel["id"],
        created["id"],
        author,
        1,
    )
    assert edit.status_code == 404
    assert retract.status_code == 404


def test_retraction_hides_content_search_activity_and_unread_but_preserves_thread(
    db_session: Session,
    client,
) -> None:
    organization, author, member, _, _, _, _ = _seed(db_session, "retract")
    channel = _channel(client, organization, author)
    sentinel = f"retract-{uuid.uuid4().hex}"
    root = _message(
        client,
        organization,
        channel["id"],
        author,
        f"{sentinel} @{member.email}",
        "lifecycle-retract-root",
    )

    _as(member)
    before_unread = client.get(
        f"/api/v1/organizations/{organization.id}/native-conversation/channels"
    )
    assert before_unread.status_code == 200
    summary = next(row for row in before_unread.json() if row["channel_id"] == channel["id"])
    assert summary["unread_count"] == 1

    reply = client.post(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{root['id']}/replies",
        headers={"Idempotency-Key": "lifecycle-existing-reply"},
        json={"body": "Existing reply survives root retraction."},
    )
    assert reply.status_code == 201

    retracted = _retract(
        client,
        organization,
        channel["id"],
        root["id"],
        author,
        1,
    )
    assert retracted.status_code == 200
    tombstone = retracted.json()
    assert tombstone["revision"] == 2
    assert tombstone["deleted_at"] is not None
    assert tombstone["body"] == ""
    assert tombstone["body_sha256"] == ""
    assert tombstone["mentions"] == []
    assert tombstone["reactions"] == []
    assert tombstone["can_edit"] is False
    assert tombstone["can_delete"] is False

    hidden_search = _search(client, organization, author, sentinel)
    assert hidden_search.status_code == 200
    assert hidden_search.json()["results"] == []

    after_activity = list_activity(
        db_session,
        organization_id=organization.id,
        user_id=member.id,
        limit=20,
    )
    assert all(item.kind != ActivityKind.MENTION for item in after_activity)

    _as(member)
    roots = client.get(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages"
    )
    replies = client.get(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{root['id']}/replies"
    )
    blocked_reply = client.post(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{root['id']}/replies",
        headers={"Idempotency-Key": "lifecycle-blocked-reply"},
        json={"body": "Must not attach to a retracted root."},
    )
    blocked_reaction = client.put(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{root['id']}/reaction",
        json={"reaction": "👍"},
    )
    assert roots.status_code == 200
    root_view = next(row for row in roots.json() if row["id"] == root["id"])
    assert root_view["body"] == ""
    assert root_view["reply_count"] == 1
    assert replies.status_code == 200
    assert [row["id"] for row in replies.json()] == [reply.json()["id"]]
    assert blocked_reply.status_code == 404
    assert blocked_reaction.status_code == 404

    after_unread = client.get(
        f"/api/v1/organizations/{organization.id}/native-conversation/channels"
    )
    summary = next(row for row in after_unread.json() if row["channel_id"] == channel["id"])
    assert summary["unread_count"] == 0

    revisions = list(
        db_session.scalars(
            select(NativeMessageRevision)
            .where(NativeMessageRevision.message_id == uuid.UUID(root["id"]))
            .order_by(NativeMessageRevision.revision)
        )
    )
    assert len(revisions) == 1
    assert revisions[0].action == NativeMessageRevisionAction.RETRACT
    assert sentinel in revisions[0].body

    audit = db_session.scalar(
        select(SecurityAuditEvent).where(
            SecurityAuditEvent.organization_id == organization.id,
            SecurityAuditEvent.event_type == "native_chat.message.retracted",
        )
    )
    assert audit is not None
    assert sentinel not in json.dumps(audit.metadata_json, sort_keys=True)


def test_message_revision_history_obeys_derived_retention_and_legal_hold(
    db_session: Session,
    client,
) -> None:
    organization, author, _, _, _, _, _ = _seed(db_session, "retention")
    channel = _channel(client, organization, author)
    created = _message(
        client,
        organization,
        channel["id"],
        author,
        "Original revision retained under policy.",
        "lifecycle-retention",
    )
    edited = _edit(
        client,
        organization,
        channel["id"],
        created["id"],
        author,
        "Current revision remains visible.",
        1,
    )
    assert edited.status_code == 200

    revision = db_session.scalar(
        select(NativeMessageRevision).where(
            NativeMessageRevision.message_id == uuid.UUID(created["id"])
        )
    )
    assert revision is not None
    now = datetime.now(UTC)
    revision.created_at = now - timedelta(days=3)
    db_session.commit()

    set_retention_policy(
        db_session,
        organization_id=organization.id,
        actor_user_id=author.id,
        raw_event_days=None,
        derived_content_days=1,
        audit_event_days=None,
        private_message_days=None,
        legal_hold=True,
    )
    held_run = run_retention_once(
        db_session,
        organization_id=organization.id,
        at=now,
        actor_user_id=author.id,
    )
    assert held_run is not None
    assert held_run.native_message_revisions_deleted == 0
    assert db_session.get(NativeMessageRevision, revision.id) is not None

    set_retention_policy(
        db_session,
        organization_id=organization.id,
        actor_user_id=author.id,
        raw_event_days=None,
        derived_content_days=1,
        audit_event_days=None,
        private_message_days=None,
        legal_hold=False,
    )
    purge_run = run_retention_once(
        db_session,
        organization_id=organization.id,
        at=now,
        actor_user_id=author.id,
    )
    assert purge_run is not None
    assert purge_run.native_message_revisions_deleted == 1
    assert db_session.get(NativeMessageRevision, revision.id) is None
