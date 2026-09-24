import json
import logging
import uuid

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.data_governance import DataGovernanceError, append_audit_event

security_logger = logging.getLogger("brain.security")


def _string(value: uuid.UUID | str | None) -> str | None:
    return str(value) if value is not None else None


def audit_authorization_decision(
    *,
    allowed: bool,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    permission: str,
    reason: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    db: Session | None = None,
) -> None:
    payload = {
        "event": "authorization.decision",
        "allowed": allowed,
        "organization_id": _string(organization_id),
        "actor_user_id": _string(actor_user_id),
        "permission": permission,
        "reason": reason,
        "resource_type": resource_type,
        "resource_id": resource_id,
    }
    message = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if allowed:
        security_logger.debug(message)
        return
    security_logger.warning(message)
    if db is None:
        return
    try:
        append_audit_event(
            db,
            organization_id=organization_id,
            event_key=f"authorization.denied:{uuid.uuid4()}",
            event_type="authorization.denied",
            outcome="denied",
            actor_user_id=actor_user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata={"permission": permission, "reason": reason},
        )
    except (DataGovernanceError, SQLAlchemyError):
        security_logger.exception("Failed to persist authorization denial audit event")


def audit_acl_change(
    *,
    action: str,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    target_user_id: uuid.UUID,
    resource_type: str,
    resource_id: str,
    access: str,
    db: Session | None = None,
    required: bool = False,
) -> None:
    payload = {
        "event": f"resource_acl.{action}",
        "organization_id": _string(organization_id),
        "actor_user_id": _string(actor_user_id),
        "target_user_id": _string(target_user_id),
        "resource_type": resource_type,
        "resource_id": resource_id,
        "access": access,
    }
    security_logger.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    if db is None:
        if required:
            raise DataGovernanceError("Durable ACL audit requires a database session")
        return
    try:
        append_audit_event(
            db,
            organization_id=organization_id,
            event_key=f"resource_acl.{action}:{uuid.uuid4()}",
            event_type=f"resource_acl.{action}",
            outcome="succeeded",
            actor_user_id=actor_user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata={"target_user_id": target_user_id, "access": access},
        )
    except (DataGovernanceError, SQLAlchemyError):
        security_logger.exception("Failed to persist resource ACL audit event")
        if required:
            raise
