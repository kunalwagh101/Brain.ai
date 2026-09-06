import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.identity_resolution import observe_canonical_actor
from app.models import CanonicalEvent, RawEvent, RawEventStatus
from app.work_graph import project_canonical_event

CANONICAL_EVENT_SCHEMA_VERSION = 1


class CanonicalizationError(RuntimeError):
    """Raised when a raw event cannot be mapped into the canonical contract."""


@dataclass(frozen=True, slots=True)
class CanonicalizeResult:
    event: CanonicalEvent | None
    created: bool
    quarantined: bool


def _json_payload(raw_event: RawEvent) -> dict[str, object]:
    try:
        payload = json.loads(raw_event.raw_payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CanonicalizationError("invalid_json") from exc
    if not isinstance(payload, dict):
        raise CanonicalizationError("invalid_payload_shape")
    return payload


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _identifier(value: object) -> str | None:
    if isinstance(value, (str, int)):
        text = str(value)
        return text if text else None
    return None


def _datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _provenance(raw_event: RawEvent) -> dict[str, object]:
    return {
        "raw_event_id": str(raw_event.id),
        "integration_connection_id": str(raw_event.integration_connection_id),
        "payload_sha256": raw_event.payload_sha256,
        "delivery_kind": raw_event.delivery_kind,
        "received_at": raw_event.received_at.isoformat() if raw_event.received_at else None,
    }


def _slack_data(raw_event: RawEvent, payload: dict[str, object]) -> dict[str, object]:
    if raw_event.delivery_kind == "webhook":
        event = _as_dict(payload.get("event"))
        channel_id = _string(event.get("channel"))
        source = event
    else:
        event = _as_dict(payload.get("message"))
        channel_id = _string(payload.get("channel_id"))
        source = event

    source_type = raw_event.source_event_type
    if source_type == "message":
        subtype = _string(event.get("subtype"))
        if subtype == "message_changed":
            action = "updated"
            current = _as_dict(event.get("message"))
        elif subtype == "message_deleted":
            action = "deleted"
            current = _as_dict(event.get("previous_message"))
        else:
            action = "created"
            current = event
        message_ts = _string(current.get("ts")) or _string(event.get("event_ts"))
        if not channel_id or not message_ts:
            raise CanonicalizationError("slack_message_missing_identity")
        actor_id = _string(current.get("user")) or _string(event.get("user"))
        bot_id = _string(current.get("bot_id")) or _string(event.get("bot_id"))
        actor_type = "slack_user" if actor_id else "slack_bot" if bot_id else "unknown"
        actor_external_id = actor_id or bot_id
        return {
            "event_type": f"message.{action}",
            "action": action,
            "actor_type": actor_type,
            "actor_external_id": actor_external_id,
            "actor_display_name": None,
            "object_type": "message",
            "object_external_id": f"{channel_id}:{message_ts}",
            "object_display_name": None,
            "occurred_at": raw_event.source_timestamp,
            "event_metadata": {
                "channel_id": channel_id,
                "message_ts": message_ts,
                "thread_ts": _string(current.get("thread_ts")),
                "subtype": subtype,
                "text": _string(current.get("text")),
            },
        }

    if source_type in {"member_joined_channel", "member_left_channel"}:
        if not channel_id:
            raise CanonicalizationError("slack_membership_missing_channel")
        user_id = _string(source.get("user"))
        if not user_id:
            raise CanonicalizationError("slack_membership_missing_user")
        joined = source_type == "member_joined_channel"
        action = "joined" if joined else "left"
        return {
            "event_type": f"channel.member_{action}",
            "action": action,
            "actor_type": "slack_user",
            "actor_external_id": user_id,
            "actor_display_name": None,
            "object_type": "channel",
            "object_external_id": channel_id,
            "object_display_name": None,
            "occurred_at": raw_event.source_timestamp,
            "event_metadata": {"channel_id": channel_id},
        }

    raise CanonicalizationError(f"unsupported_slack_event:{source_type}")


def _github_actor(
    payload: dict[str, object],
    item: dict[str, object],
) -> tuple[str, str | None, str | None]:
    actor = _as_dict(payload.get("sender")) or _as_dict(item.get("user"))
    if not actor:
        actor = _as_dict(item.get("author"))
    actor_id = _identifier(actor.get("id")) or _string(actor.get("login"))
    actor_name = _string(actor.get("login")) or _string(actor.get("name"))
    return "github_user", actor_id, actor_name


def _github_data(raw_event: RawEvent, payload: dict[str, object]) -> dict[str, object]:
    source_type = raw_event.source_event_type
    if source_type.startswith("backfill."):
        item = _as_dict(payload.get("item"))
        repository = _as_dict(payload.get("repository"))
    else:
        item = payload
        repository = _as_dict(payload.get("repository"))

    actor_type, actor_id, actor_name = _github_actor(payload, item)
    repo_id = _identifier(repository.get("id"))
    repo_name = _string(repository.get("full_name")) or _string(repository.get("name"))
    source_action = _string(payload.get("action"))

    if source_type == "push":
        ref = _string(payload.get("ref")) or "unknown"
        return {
            "event_type": "commit.pushed",
            "action": "pushed",
            "actor_type": actor_type,
            "actor_external_id": actor_id,
            "actor_display_name": actor_name,
            "object_type": "git_ref",
            "object_external_id": f"{repo_id or repo_name}:{ref}",
            "object_display_name": ref,
            "occurred_at": raw_event.source_timestamp,
            "event_metadata": {
                "repository_id": repo_id,
                "repository": repo_name,
                "ref": ref,
                "before": _string(payload.get("before")),
                "after": _string(payload.get("after")),
                "commit_count": len(payload.get("commits", []))
                if isinstance(payload.get("commits"), list)
                else 0,
            },
        }

    mappings: dict[str, tuple[str, str, str, object]] = {
        "pull_request": (
            "pull_request",
            source_action or "updated",
            "pull_request",
            payload.get("pull_request"),
        ),
        "issues": (
            "issue",
            source_action or "updated",
            "issue",
            payload.get("issue"),
        ),
        "deployment": (
            "deployment",
            source_action or "created",
            "deployment",
            payload.get("deployment"),
        ),
        "deployment_status": (
            "deployment",
            "status_changed",
            "deployment_status",
            payload.get("deployment_status"),
        ),
        "workflow_run": (
            "workflow_run",
            source_action or "updated",
            "workflow_run",
            payload.get("workflow_run"),
        ),
        "repository": (
            "repository",
            source_action or "updated",
            "repository",
            payload.get("repository"),
        ),
        "backfill.repository": ("repository", "observed", "repository", item),
        "backfill.commit": ("commit", "observed", "commit", item),
        "backfill.pull_request": ("pull_request", "observed", "pull_request", item),
        "backfill.issue": ("issue", "observed", "issue", item),
        "backfill.deployment": ("deployment", "observed", "deployment", item),
    }
    mapped = mappings.get(source_type)
    if mapped is None:
        raise CanonicalizationError(f"unsupported_github_event:{source_type}")

    event_prefix, action, object_type, object_value = mapped
    obj = _as_dict(object_value)
    object_id = (
        _identifier(obj.get("id"))
        or _identifier(obj.get("number"))
        or _string(obj.get("sha"))
        or repo_id
        or repo_name
    )
    if not object_id:
        raise CanonicalizationError("github_event_missing_object_identity")
    object_name = (
        _string(obj.get("title"))
        or _string(obj.get("name"))
        or _string(obj.get("sha"))
        or repo_name
    )
    occurred_at = (
        raw_event.source_timestamp
        or _datetime(obj.get("updated_at"))
        or _datetime(obj.get("created_at"))
    )
    return {
        "event_type": f"{event_prefix}.{action}",
        "action": action,
        "actor_type": actor_type,
        "actor_external_id": actor_id,
        "actor_display_name": actor_name,
        "object_type": object_type,
        "object_external_id": object_id,
        "object_display_name": object_name,
        "occurred_at": occurred_at,
        "event_metadata": {
            "repository_id": repo_id,
            "repository": repo_name,
            "source_action": source_action,
            "html_url": _string(obj.get("html_url")),
            "state": _string(obj.get("state")),
        },
    }


def _observe_persisted_actor(db: Session, event: CanonicalEvent) -> None:
    if event.source_identity_id is None:
        observe_canonical_actor(db, event)
    project_canonical_event(db, event)


def canonicalize_raw_event(db: Session, raw_event: RawEvent) -> CanonicalizeResult:
    existing = db.scalar(
        select(CanonicalEvent).where(CanonicalEvent.raw_event_id == raw_event.id)
    )
    if existing is not None:
        if raw_event.processing_status != RawEventStatus.PROCESSED:
            raw_event.processing_status = RawEventStatus.PROCESSED
            raw_event.last_error_code = None
            db.commit()
        _observe_persisted_actor(db, existing)
        return CanonicalizeResult(event=existing, created=False, quarantined=False)

    raw_event.processing_attempts += 1
    try:
        payload = _json_payload(raw_event)
        if raw_event.provider == "slack":
            data = _slack_data(raw_event, payload)
        elif raw_event.provider == "github":
            data = _github_data(raw_event, payload)
        else:
            raise CanonicalizationError(f"unsupported_provider:{raw_event.provider}")
    except CanonicalizationError as exc:
        raw_event.processing_status = RawEventStatus.QUARANTINED
        raw_event.last_error_code = str(exc)[:128]
        db.commit()
        db.refresh(raw_event)
        return CanonicalizeResult(event=None, created=False, quarantined=True)

    canonical = CanonicalEvent(
        organization_id=raw_event.organization_id,
        raw_event_id=raw_event.id,
        integration_connection_id=raw_event.integration_connection_id,
        schema_version=CANONICAL_EVENT_SCHEMA_VERSION,
        event_type=str(data["event_type"]),
        action=str(data["action"]),
        actor_type=str(data["actor_type"]),
        actor_external_id=data["actor_external_id"],
        actor_display_name=data["actor_display_name"],
        object_type=str(data["object_type"]),
        object_external_id=str(data["object_external_id"]),
        object_display_name=data["object_display_name"],
        source_provider=raw_event.provider,
        source_event_id=raw_event.source_event_id,
        source_event_type=raw_event.source_event_type,
        occurred_at=data["occurred_at"],
        source_visibility=raw_event.source_visibility,
        source_acl=list(raw_event.source_acl),
        provenance=_provenance(raw_event),
        event_metadata=data["event_metadata"],
    )
    db.add(canonical)
    raw_event.processing_status = RawEventStatus.PROCESSED
    raw_event.last_error_code = None
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(CanonicalEvent).where(CanonicalEvent.raw_event_id == raw_event.id)
        )
        if existing is None:
            raise
        raw_event.processing_status = RawEventStatus.PROCESSED
        raw_event.last_error_code = None
        db.commit()
        _observe_persisted_actor(db, existing)
        return CanonicalizeResult(event=existing, created=False, quarantined=False)

    db.refresh(canonical)
    db.refresh(raw_event)
    _observe_persisted_actor(db, canonical)
    db.refresh(canonical)
    return CanonicalizeResult(event=canonical, created=True, quarantined=False)
