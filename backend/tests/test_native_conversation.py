import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, User
from app.native_chat_models import NativeMessage
from app.native_conversation_models import NativeMessageMention


def _seed(db: Session, suffix: str):
    organization = Organization(
        name=f"Conversation UX {suffix}",
        slug=f"conversation-ux-{suffix}-{uuid.uuid4().hex[:6]}",
    )
    owner = User(
        email=f"owner-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Owner",
    )
    member = User(
        email=f"member-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Member",
    )
    outsider = User(
        email=f"outsider-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Outsider",
    )
    db.add_all([organization, owner, member, outsider])
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
        ]
    )
    db.commit()
    return organization, owner, member, outsider


def _as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _channel(client, organization, user, visibility="organization"):
    _as(user)
    response = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels",
        json={
            "name": f"channel-{uuid.uuid4().hex[:7]}",
            "visibility": visibility,
        },
    )
    assert response.status_code == 201
    return response.json()


def _root(client, organization, channel_id, user, body, key):
    _as(user)
    return client.post(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel_id}/messages",
        headers={"Idempotency-Key": key},
        json={"body": body},
    )


def _reply(client, organization, channel_id, root_id, user, body, key):
    _as(user)
    return client.post(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel_id}/messages/{root_id}/replies",
        headers={"Idempotency-Key": key},
        json={"body": body},
    )


def test_threads_and_exact_mentions_are_scoped_and_idempotent(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _ = _seed(db_session, "thread")
    channel = _channel(client, organization, owner)
    body = f"Please review @{member.email} and @{member.email}."
    root = _root(
        client,
        organization,
        channel["id"],
        owner,
        body,
        "thread-root",
    )
    assert root.status_code == 201
    assert root.json()["thread_root_id"] is None
    assert [item["user_id"] for item in root.json()["mentions"]] == [str(member.id)]

    reply = _reply(
        client,
        organization,
        channel["id"],
        root.json()["id"],
        member,
        "Reviewed. Looks safe.",
        "thread-reply",
    )
    assert reply.status_code == 201
    assert reply.json()["thread_root_id"] == root.json()["id"]
    persisted_root = db_session.get(NativeMessage, uuid.UUID(root.json()["id"]))
    persisted_reply = db_session.get(NativeMessage, uuid.UUID(reply.json()["id"]))
    assert persisted_root is not None
    assert persisted_reply is not None
    assert persisted_reply.message_sequence > persisted_root.message_sequence

    repeated = _reply(
        client,
        organization,
        channel["id"],
        root.json()["id"],
        member,
        "Reviewed. Looks safe.",
        "thread-reply",
    )
    assert repeated.status_code == 201
    assert repeated.json()["id"] == reply.json()["id"]

    _as(member)
    roots = client.get(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages"
    )
    replies = client.get(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{root.json()['id']}/replies"
    )
    nested = _reply(
        client,
        organization,
        channel["id"],
        reply.json()["id"],
        member,
        "Nested replies are rejected.",
        "nested-reply",
    )
    assert [row["id"] for row in roots.json()] == [root.json()["id"]]
    assert roots.json()[0]["reply_count"] == 1
    assert [row["id"] for row in replies.json()] == [reply.json()["id"]]
    assert nested.status_code == 404


def test_all_message_entry_points_share_exact_mention_resolution(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _ = _seed(db_session, "legacy-mention")
    channel = _channel(client, organization, owner)
    _as(owner)
    created = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel['id']}/messages",
        headers={"Idempotency-Key": "legacy-mention"},
        json={"body": f"Legacy path still resolves @{member.email}."},
    )
    assert created.status_code == 201
    mentions = list(
        db_session.scalars(
            select(NativeMessageMention).where(
                NativeMessageMention.message_id == uuid.UUID(created.json()["id"])
            )
        )
    )
    assert [row.mentioned_user_id for row in mentions] == [member.id]


def test_restricted_channel_does_not_resolve_unauthorized_mentions(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _ = _seed(db_session, "hidden-mention")
    channel = _channel(client, organization, owner, visibility="restricted")
    message = _root(
        client,
        organization,
        channel["id"],
        owner,
        f"Do not notify @{member.email} or @missing@example.com.",
        "hidden-mention",
    )
    assert message.status_code == 201
    assert message.json()["mentions"] == []


def test_reactions_are_allow_listed_per_user_and_idempotent(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _ = _seed(db_session, "reaction")
    channel = _channel(client, organization, owner)
    root = _root(
        client,
        organization,
        channel["id"],
        owner,
        "React to this.",
        "reaction-root",
    ).json()
    endpoint = (
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{root['id']}/reaction"
    )

    _as(owner)
    first = client.put(endpoint, json={"reaction": "👍"})
    duplicate = client.put(endpoint, json={"reaction": "👍"})
    _as(member)
    second_user = client.put(endpoint, json={"reaction": "👍"})
    disallowed = client.put(endpoint, json={"reaction": "<script>"})
    removed = client.request("DELETE", endpoint, json={"reaction": "👍"})

    assert first.status_code == 200
    assert duplicate.json()["count"] == 1
    assert second_user.json()["count"] == 2
    assert disallowed.status_code == 400
    assert removed.status_code == 204

    _as(owner)
    roots = client.get(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages"
    )
    assert roots.json()[0]["reactions"] == [
        {"reaction": "👍", "count": 1, "reacted_by_me": True}
    ]


def test_unread_state_is_per_user_excludes_own_and_never_moves_back(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _ = _seed(db_session, "unread")
    channel = _channel(client, organization, owner)
    first = _root(
        client,
        organization,
        channel["id"],
        owner,
        "First update.",
        "unread-first",
    ).json()
    second = _root(
        client,
        organization,
        channel["id"],
        owner,
        "Second update.",
        "unread-second",
    ).json()
    summary_url = (
        f"/api/v1/organizations/{organization.id}/native-conversation/channels"
    )

    _as(owner)
    owner_summary = client.get(summary_url)
    _as(member)
    member_summary = client.get(summary_url)
    assert owner_summary.json()[0]["unread_count"] == 0
    assert owner_summary.json()[0]["first_unread_message_id"] is None
    assert member_summary.json()[0]["unread_count"] == 2
    assert member_summary.json()[0]["first_unread_message_id"] == first["id"]
    assert member_summary.json()[0]["latest_message_id"] == second["id"]

    read_url = (
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/read"
    )
    read_first = client.post(
        read_url,
        json={"through_message_id": first["id"]},
    )
    assert read_first.json()["unread_count"] == 1
    assert read_first.json()["first_unread_message_id"] == second["id"]
    assert read_first.json()["latest_message_id"] == second["id"]

    read_second = client.post(
        read_url,
        json={"through_message_id": second["id"]},
    )
    stale_read = client.post(
        read_url,
        json={"through_message_id": first["id"]},
    )
    assert read_second.json()["unread_count"] == 0
    assert read_second.json()["first_unread_message_id"] is None
    assert stale_read.json()["last_read_at"] == read_second.json()["last_read_at"]

    third = _root(
        client,
        organization,
        channel["id"],
        owner,
        "Third update.",
        "unread-third",
    ).json()
    _as(member)
    latest_summary = client.get(summary_url).json()[0]
    assert latest_summary["unread_count"] == 1
    assert latest_summary["first_unread_message_id"] == third["id"]
    assert latest_summary["latest_message_id"] == third["id"]


def test_first_unread_can_be_a_thread_reply(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _ = _seed(db_session, "unread-thread")
    channel = _channel(client, organization, owner)
    root = _root(
        client,
        organization,
        channel["id"],
        owner,
        "Read this root first.",
        "unread-thread-root",
    ).json()

    _as(member)
    read_url = (
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/read"
    )
    marked = client.post(read_url, json={"through_message_id": root["id"]})
    assert marked.status_code == 200

    reply = _reply(
        client,
        organization,
        channel["id"],
        root["id"],
        owner,
        "This reply should be the first unread item.",
        "unread-thread-reply",
    ).json()

    _as(member)
    summary = client.get(
        f"/api/v1/organizations/{organization.id}/native-conversation/channels"
    )
    assert summary.status_code == 200
    channel_summary = next(
        row for row in summary.json() if row["channel_id"] == channel["id"]
    )
    assert channel_summary["unread_count"] == 1
    assert channel_summary["first_unread_message_id"] == reply["id"]


def test_revoked_restricted_member_gets_no_conversation_content(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _ = _seed(db_session, "revoked")
    channel = _channel(client, organization, owner, visibility="restricted")
    _as(owner)
    grant = client.put(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel['id']}/members/{member.id}",
        json={"access": "write"},
    )
    assert grant.status_code == 200
    root = _root(
        client,
        organization,
        channel["id"],
        owner,
        f"Restricted note for @{member.email}.",
        "restricted-root",
    ).json()
    reply = _reply(
        client,
        organization,
        channel["id"],
        root["id"],
        member,
        "Acknowledged.",
        "restricted-reply",
    )
    assert reply.status_code == 201

    _as(owner)
    revoked = client.delete(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel['id']}/members/{member.id}"
    )
    assert revoked.status_code == 204

    _as(member)
    roots_url = (
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages"
    )
    replies_url = f"{roots_url}/{root['id']}/replies"
    reaction_url = f"{roots_url}/{root['id']}/reaction"
    read_url = (
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/read"
    )
    assert client.get(roots_url).status_code == 404
    assert client.get(replies_url).status_code == 404
    assert client.put(reaction_url, json={"reaction": "👍"}).status_code in {403, 404}
    assert (
        client.post(read_url, json={"through_message_id": root["id"]}).status_code
        == 404
    )
    summary = client.get(
        f"/api/v1/organizations/{organization.id}/native-conversation/channels"
    )
    assert channel["id"] not in summary.text
    assert "Restricted note" not in summary.text


def test_cross_tenant_message_ids_never_resolve(
    db_session: Session,
    client,
) -> None:
    organization_a, owner_a, _, _ = _seed(db_session, "tenant-a")
    organization_b, owner_b, _, _ = _seed(db_session, "tenant-b")
    channel = _channel(client, organization_a, owner_a)
    root = _root(
        client,
        organization_a,
        channel["id"],
        owner_a,
        "Tenant A only.",
        "tenant-a-root",
    ).json()

    _as(owner_b)
    replies = client.get(
        f"/api/v1/organizations/{organization_b.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{root['id']}/replies"
    )
    reaction = client.put(
        f"/api/v1/organizations/{organization_b.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{root['id']}/reaction",
        json={"reaction": "👍"},
    )
    read = client.post(
        f"/api/v1/organizations/{organization_b.id}/native-conversation/"
        f"channels/{channel['id']}/read",
        json={"through_message_id": root["id"]},
    )
    assert replies.status_code == 404
    assert reaction.status_code == 404
    assert read.status_code == 404


def test_single_message_read_respects_current_channel_access(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _ = _seed(db_session, "deep-link")
    channel = _channel(client, organization, owner, visibility="restricted")

    _as(owner)
    invite = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel['id']}/members",
        json={"email": member.email, "access": "read"},
    )
    assert invite.status_code == 201

    message = _root(
        client,
        organization,
        channel["id"],
        owner,
        "Exact deep-link target.",
        "deep-link-target",
    )
    assert message.status_code == 201
    message_id = message.json()["id"]
    endpoint = (
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{message_id}"
    )

    _as(member)
    visible = client.get(endpoint)
    assert visible.status_code == 200
    assert visible.json()["id"] == message_id

    _as(owner)
    revoked = client.delete(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel['id']}/members/{member.id}"
    )
    assert revoked.status_code == 204

    _as(member)
    hidden = client.get(endpoint)
    assert hidden.status_code == 404

def test_native_root_history_uses_stable_sequence_cursor(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _ = _seed(db_session, "history-page")
    channel = _channel(client, organization, owner)
    created = [
        _root(
            client,
            organization,
            channel["id"],
            owner,
            f"History root {index}",
            f"history-root-{index}",
        ).json()
        for index in range(1, 6)
    ]

    _as(member)
    endpoint = (
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages"
    )
    first_page = client.get(endpoint, params={"limit": 2})
    assert first_page.status_code == 200
    assert [item["id"] for item in first_page.json()] == [
        created[3]["id"],
        created[4]["id"],
    ]

    before_sequence = first_page.json()[0]["message_sequence"]
    second_page = client.get(
        endpoint,
        params={"limit": 2, "before_sequence": before_sequence},
    )
    assert second_page.status_code == 200
    assert [item["id"] for item in second_page.json()] == [
        created[1]["id"],
        created[2]["id"],
    ]
    assert {
        item["id"] for item in first_page.json()
    }.isdisjoint({item["id"] for item in second_page.json()})

    third_page = client.get(
        endpoint,
        params={
            "limit": 2,
            "before_sequence": second_page.json()[0]["message_sequence"],
        },
    )
    assert [item["id"] for item in third_page.json()] == [created[0]["id"]]
    assert client.get(
        endpoint,
        params={"limit": 2, "before_sequence": 0},
    ).status_code == 422

def test_thread_reply_history_uses_stable_sequence_cursor(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _ = _seed(db_session, "thread-page")
    channel = _channel(client, organization, owner)
    root = _root(
        client,
        organization,
        channel["id"],
        owner,
        "Thread pagination root",
        "thread-page-root",
    ).json()
    created = []
    for index in range(1, 6):
        reply = _reply(
            client,
            organization,
            channel["id"],
            root["id"],
            member,
            f"Reply {index}",
            f"thread-page-reply-{index}",
        )
        assert reply.status_code == 201
        created.append(reply.json())

    _as(owner)
    endpoint = (
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{root['id']}/replies"
    )
    first = client.get(endpoint, params={"limit": 2})
    assert first.status_code == 200
    assert [item["id"] for item in first.json()] == [
        created[3]["id"],
        created[4]["id"],
    ]

    second = client.get(
        endpoint,
        params={
            "limit": 2,
            "before_sequence": first.json()[0]["message_sequence"],
        },
    )
    third = client.get(
        endpoint,
        params={
            "limit": 2,
            "before_sequence": second.json()[0]["message_sequence"],
        },
    )
    invalid = client.get(endpoint, params={"before_sequence": 0})
    assert [item["id"] for item in second.json()] == [
        created[1]["id"],
        created[2]["id"],
    ]
    assert [item["id"] for item in third.json()] == [created[0]["id"]]
    assert {
        item["id"] for item in first.json()
    }.isdisjoint({item["id"] for item in second.json()})
    assert invalid.status_code == 422

def test_thread_unread_state_is_independent_monotonic_and_excludes_own_replies(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _ = _seed(db_session, "thread-unread")
    channel = _channel(client, organization, owner)
    root = _root(
        client,
        organization,
        channel["id"],
        owner,
        "Thread unread root",
        "thread-unread-root",
    ).json()
    first = _reply(
        client,
        organization,
        channel["id"],
        root["id"],
        member,
        "First reply before thread follow",
        "thread-unread-first",
    ).json()

    _as(owner)
    roots_endpoint = (
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages"
    )
    root_before = client.get(roots_endpoint)
    assert root_before.status_code == 200
    row = next(item for item in root_before.json() if item["id"] == root["id"])
    assert row["thread_unread_count"] == 0
    assert row["thread_first_unread_reply_id"] is None
    assert row["thread_latest_reply_id"] == first["id"]

    read_endpoint = (
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{root['id']}/thread-read"
    )
    followed = client.post(
        read_endpoint,
        json={"through_message_id": first["id"]},
    )
    assert followed.status_code == 200
    assert followed.json()["unread_count"] == 0

    second = _reply(
        client,
        organization,
        channel["id"],
        root["id"],
        member,
        "Unread reply from member",
        "thread-unread-second",
    ).json()
    mine = _reply(
        client,
        organization,
        channel["id"],
        root["id"],
        owner,
        "Owner reply does not count unread",
        "thread-unread-mine",
    ).json()

    _as(owner)
    after = client.get(roots_endpoint)
    row = next(item for item in after.json() if item["id"] == root["id"])
    assert row["thread_unread_count"] == 1
    assert row["thread_first_unread_reply_id"] == second["id"]
    assert row["thread_latest_reply_id"] == mine["id"]

    latest = client.post(
        read_endpoint,
        json={"through_message_id": mine["id"]},
    )
    stale = client.post(
        read_endpoint,
        json={"through_message_id": first["id"]},
    )
    assert latest.status_code == 200
    assert latest.json()["unread_count"] == 0
    assert stale.status_code == 200
    assert stale.json()["unread_count"] == 0

    other_root = _root(
        client,
        organization,
        channel["id"],
        owner,
        "Other root",
        "thread-unread-other-root",
    ).json()
    other_reply = _reply(
        client,
        organization,
        channel["id"],
        other_root["id"],
        member,
        "Other reply",
        "thread-unread-other-reply",
    ).json()
    _as(owner)
    cross_root = client.post(
        read_endpoint,
        json={"through_message_id": other_reply["id"]},
    )
    assert cross_root.status_code == 404


def test_retracted_reply_is_removed_from_thread_unread_attention(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _ = _seed(db_session, "thread-unread-retract")
    channel = _channel(client, organization, owner)
    root = _root(
        client,
        organization,
        channel["id"],
        owner,
        "Retraction root",
        "thread-retract-root",
    ).json()
    baseline = _reply(
        client,
        organization,
        channel["id"],
        root["id"],
        member,
        "Baseline",
        "thread-retract-baseline",
    ).json()

    _as(owner)
    read_endpoint = (
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{root['id']}/thread-read"
    )
    assert client.post(
        read_endpoint,
        json={"through_message_id": baseline["id"]},
    ).status_code == 200

    unread = _reply(
        client,
        organization,
        channel["id"],
        root["id"],
        member,
        "Temporary unread reply",
        "thread-retract-unread",
    ).json()
    _as(owner)
    roots_endpoint = (
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages"
    )
    row = next(
        item for item in client.get(roots_endpoint).json()
        if item["id"] == root["id"]
    )
    assert row["thread_unread_count"] == 1

    _as(member)
    retracted = client.request(
        "DELETE",
        (
            f"/api/v1/organizations/{organization.id}/native-conversation/"
            f"channels/{channel['id']}/messages/{unread['id']}"
        ),
        json={"expected_revision": unread["revision"]},
    )
    assert retracted.status_code == 200

    _as(owner)
    row = next(
        item for item in client.get(roots_endpoint).json()
        if item["id"] == root["id"]
    )
    assert row["thread_unread_count"] == 0
    assert row["thread_first_unread_reply_id"] is None
