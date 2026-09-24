import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.evidence_models import EvidenceSource, EvidenceSourceStatus
from app.main import app
from app.models import (
    Membership,
    MembershipRole,
    Organization,
    ResourceGrant,
    User,
)
from app.native_conversation_models import NativeMessageAttachment
from app.search_models import SearchDocument


def _as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _seed(db: Session, suffix: str):
    organization = Organization(
        name=f"Attachment {suffix}",
        slug=f"attachment-{suffix}-{uuid.uuid4().hex[:6]}",
    )
    other_organization = Organization(
        name=f"Other Attachment {suffix}",
        slug=f"other-attachment-{suffix}-{uuid.uuid4().hex[:6]}",
    )
    owner = User(
        email=f"attachment-owner-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Attachment Owner",
    )
    member = User(
        email=f"attachment-member-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Attachment Member",
    )
    outsider = User(
        email=f"attachment-outsider-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Attachment Outsider",
    )
    other_owner = User(
        email=f"other-owner-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Other Owner",
    )
    db.add_all(
        [
            organization,
            other_organization,
            owner,
            member,
            outsider,
            other_owner,
        ]
    )
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
            Membership(
                organization_id=organization.id,
                user_id=outsider.id,
                role=MembershipRole.MEMBER,
            ),
            Membership(
                organization_id=other_organization.id,
                user_id=other_owner.id,
                role=MembershipRole.OWNER,
            ),
        ]
    )
    db.commit()
    return organization, other_organization, owner, member, outsider, other_owner


def _channel(client, organization, actor, visibility="organization"):
    _as(actor)
    response = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels",
        json={
            "name": f"files-{uuid.uuid4().hex[:7]}",
            "visibility": visibility,
        },
    )
    assert response.status_code == 201
    return response.json()


def _upload(
    client,
    organization,
    channel_id,
    actor,
    *,
    sentinel: str,
    key: str,
):
    _as(actor)
    return client.post(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel_id}/attachments/uploads",
        headers={"Idempotency-Key": key},
        data={"kind": "document", "title": f"{sentinel}.txt"},
        files={
            "file": (
                f"{sentinel}.txt",
                f"Governed attachment sentinel {sentinel}".encode(),
                "text/plain",
            )
        },
    )


def _send(
    client,
    organization,
    channel_id,
    actor,
    *,
    body="",
    source_ids=None,
    key: str,
):
    _as(actor)
    return client.post(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel_id}/messages",
        headers={"Idempotency-Key": key},
        json={
            "body": body,
            "attachment_source_ids": source_ids or [],
        },
    )


def _search(client, organization, actor, query):
    _as(actor)
    return client.get(
        f"/api/v1/organizations/{organization.id}/search",
        params={"q": query, "mode": "keyword", "limit": 20},
    )


def test_file_only_message_reuses_governed_evidence_and_deduplicates_ids(
    db_session: Session,
    client,
) -> None:
    organization, _, owner, _, _, _ = _seed(db_session, "file-only")
    channel = _channel(client, organization, owner)
    sentinel = f"file-only-{uuid.uuid4().hex}"
    uploaded = _upload(
        client,
        organization,
        channel["id"],
        owner,
        sentinel=sentinel,
        key="file-only-upload",
    )
    assert uploaded.status_code == 201
    source_id = uploaded.json()["source_id"]

    sent = _send(
        client,
        organization,
        channel["id"],
        owner,
        source_ids=[source_id, source_id],
        key="file-only-message",
    )
    assert sent.status_code == 201
    payload = sent.json()
    assert payload["body"] == ""
    assert len(payload["attachments"]) == 1
    assert payload["attachments"][0]["source_id"] == source_id
    assert payload["attachments"][0]["filename"].endswith(".txt")
    assert "raw_content" not in payload["attachments"][0]

    rows = list(
        db_session.scalars(
            select(NativeMessageAttachment).where(
                NativeMessageAttachment.message_id == uuid.UUID(payload["id"])
            )
        )
    )
    assert len(rows) == 1

    source = db_session.get(EvidenceSource, uuid.UUID(source_id))
    assert source is not None
    assert source.native_channel_id == uuid.UUID(channel["id"])
    assert source.status == EvidenceSourceStatus.ACTIVE

    result = _search(client, organization, owner, sentinel)
    assert result.status_code == 200
    assert any(item["object_external_id"] == source_id for item in result.json()["results"])


def test_restricted_attachment_visibility_follows_live_channel_membership(
    db_session: Session,
    client,
) -> None:
    organization, _, owner, member, outsider, _ = _seed(db_session, "restricted")
    channel = _channel(client, organization, owner, visibility="restricted")
    sentinel = f"restricted-file-{uuid.uuid4().hex}"
    uploaded = _upload(
        client,
        organization,
        channel["id"],
        owner,
        sentinel=sentinel,
        key="restricted-upload",
    )
    assert uploaded.status_code == 201
    source_id = uploaded.json()["source_id"]

    _as(member)
    hidden_before = client.get(
        f"/api/v1/organizations/{organization.id}/evidence/{source_id}"
    )
    assert hidden_before.status_code == 404
    search_before = _search(client, organization, member, sentinel)
    assert search_before.status_code == 200
    assert search_before.json()["results"] == []

    _as(owner)
    invited = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel['id']}/members",
        json={"email": member.email, "access": "read"},
    )
    assert invited.status_code == 201

    _as(member)
    visible = client.get(
        f"/api/v1/organizations/{organization.id}/evidence/{source_id}"
    )
    assert visible.status_code == 200
    search_visible = _search(client, organization, member, sentinel)
    assert search_visible.status_code == 200
    assert any(
        item["object_external_id"] == source_id
        for item in search_visible.json()["results"]
    )

    documents = list(
        db_session.scalars(
            select(SearchDocument).where(
                SearchDocument.organization_id == organization.id,
                SearchDocument.object_external_id == source_id,
            )
        )
    )
    node_ids = {str(item.work_graph_node_id) for item in documents if item.work_graph_node_id}
    assert node_ids
    grants = list(
        db_session.scalars(
            select(ResourceGrant).where(
                ResourceGrant.organization_id == organization.id,
                ResourceGrant.user_id == member.id,
                ResourceGrant.resource_type == "work_graph.node",
                ResourceGrant.resource_id.in_(node_ids),
            )
        )
    )
    assert {row.resource_id for row in grants} == node_ids

    _as(owner)
    removed = client.delete(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel['id']}/members/{member.id}"
    )
    assert removed.status_code == 204

    _as(member)
    hidden_after = client.get(
        f"/api/v1/organizations/{organization.id}/evidence/{source_id}"
    )
    assert hidden_after.status_code == 404
    search_after = _search(client, organization, member, sentinel)
    assert search_after.status_code == 200
    assert search_after.json()["results"] == []

    grants_after = list(
        db_session.scalars(
            select(ResourceGrant).where(
                ResourceGrant.organization_id == organization.id,
                ResourceGrant.user_id == member.id,
                ResourceGrant.resource_type == "work_graph.node",
                ResourceGrant.resource_id.in_(node_ids),
            )
        )
    )
    assert grants_after == []

    _as(outsider)
    assert client.get(
        f"/api/v1/organizations/{organization.id}/evidence/{source_id}"
    ).status_code == 404


def test_attachment_linking_rejects_wrong_channel_tenant_deleted_and_mismatch(
    db_session: Session,
    client,
) -> None:
    (
        organization,
        other_organization,
        owner,
        _,
        _,
        other_owner,
    ) = _seed(db_session, "scope")
    channel_a = _channel(client, organization, owner, visibility="restricted")
    channel_b = _channel(client, organization, owner, visibility="restricted")
    other_channel = _channel(client, other_organization, other_owner)

    source_a = _upload(
        client,
        organization,
        channel_a["id"],
        owner,
        sentinel=f"channel-a-{uuid.uuid4().hex}",
        key="scope-a",
    )
    assert source_a.status_code == 201
    source_a_id = source_a.json()["source_id"]

    other_source = _upload(
        client,
        other_organization,
        other_channel["id"],
        other_owner,
        sentinel=f"other-org-{uuid.uuid4().hex}",
        key="scope-other",
    )
    assert other_source.status_code == 201

    wrong_channel = _send(
        client,
        organization,
        channel_b["id"],
        owner,
        body="wrong channel",
        source_ids=[source_a_id],
        key="wrong-channel-message",
    )
    assert wrong_channel.status_code == 400

    cross_tenant = _send(
        client,
        organization,
        channel_a["id"],
        owner,
        body="cross tenant",
        source_ids=[other_source.json()["source_id"]],
        key="cross-tenant-message",
    )
    assert cross_tenant.status_code == 400

    good = _send(
        client,
        organization,
        channel_a["id"],
        owner,
        body="same retry body",
        source_ids=[source_a_id],
        key="attachment-mismatch-message",
    )
    assert good.status_code == 201

    second_source = _upload(
        client,
        organization,
        channel_a["id"],
        owner,
        sentinel=f"second-{uuid.uuid4().hex}",
        key="scope-second",
    )
    assert second_source.status_code == 201
    mismatch = _send(
        client,
        organization,
        channel_a["id"],
        owner,
        body="same retry body",
        source_ids=[second_source.json()["source_id"]],
        key="attachment-mismatch-message",
    )
    assert mismatch.status_code == 409

    _as(owner)
    deleted = client.delete(
        f"/api/v1/organizations/{organization.id}/evidence/{source_a_id}"
    )
    assert deleted.status_code == 200
    deleted_link = _send(
        client,
        organization,
        channel_a["id"],
        owner,
        body="deleted evidence",
        source_ids=[source_a_id],
        key="deleted-link-message",
    )
    assert deleted_link.status_code == 400


def test_retraction_hides_attachment_card_without_deleting_evidence(
    db_session: Session,
    client,
) -> None:
    organization, _, owner, _, _, _ = _seed(db_session, "retract")
    channel = _channel(client, organization, owner)
    sentinel = f"retract-file-{uuid.uuid4().hex}"
    uploaded = _upload(
        client,
        organization,
        channel["id"],
        owner,
        sentinel=sentinel,
        key="retract-file-upload",
    )
    assert uploaded.status_code == 201
    source_id = uploaded.json()["source_id"]

    sent = _send(
        client,
        organization,
        channel["id"],
        owner,
        body="File attached",
        source_ids=[source_id],
        key="retract-file-message",
    )
    assert sent.status_code == 201
    assert sent.json()["attachments"]

    _as(owner)
    retracted = client.request(
        "DELETE",
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{sent.json()['id']}",
        json={"expected_revision": sent.json()["revision"]},
    )
    assert retracted.status_code == 200
    assert retracted.json()["attachments"] == []

    source = db_session.get(EvidenceSource, uuid.UUID(source_id))
    assert source is not None
    assert source.status == EvidenceSourceStatus.ACTIVE
    assert source.raw_content is not None
    evidence = client.get(
        f"/api/v1/organizations/{organization.id}/evidence/{source_id}"
    )
    assert evidence.status_code == 200


def test_deleted_evidence_renders_unavailable_metadata_on_existing_message(
    db_session: Session,
    client,
) -> None:
    organization, _, owner, _, _, _ = _seed(db_session, "deleted-card")
    channel = _channel(client, organization, owner)
    uploaded = _upload(
        client,
        organization,
        channel["id"],
        owner,
        sentinel=f"deleted-card-{uuid.uuid4().hex}",
        key="deleted-card-upload",
    )
    assert uploaded.status_code == 201
    source_id = uploaded.json()["source_id"]
    sent = _send(
        client,
        organization,
        channel["id"],
        owner,
        body="Delete the evidence later",
        source_ids=[source_id],
        key="deleted-card-message",
    )
    assert sent.status_code == 201

    _as(owner)
    deleted = client.delete(
        f"/api/v1/organizations/{organization.id}/evidence/{source_id}"
    )
    assert deleted.status_code == 200

    read = client.get(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{sent.json()['id']}"
    )
    assert read.status_code == 200
    attachment = read.json()["attachments"][0]
    assert attachment["source_id"] == source_id
    assert attachment["status"] == "deleted"
    assert attachment["retrieval_available"] is False


def test_channel_upload_idempotency_is_bound_to_channel_scope(
    db_session: Session,
    client,
) -> None:
    organization, _, owner, _, _, _ = _seed(db_session, "upload-idempotency")
    channel_a = _channel(client, organization, owner)
    channel_b = _channel(client, organization, owner)
    sentinel = f"idempotent-file-{uuid.uuid4().hex}"

    first = _upload(
        client,
        organization,
        channel_a["id"],
        owner,
        sentinel=sentinel,
        key="shared-upload-key",
    )
    replay = _upload(
        client,
        organization,
        channel_a["id"],
        owner,
        sentinel=sentinel,
        key="shared-upload-key",
    )
    wrong_scope = _upload(
        client,
        organization,
        channel_b["id"],
        owner,
        sentinel=sentinel,
        key="shared-upload-key",
    )
    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["source_id"] == first.json()["source_id"]
    assert wrong_scope.status_code == 409
