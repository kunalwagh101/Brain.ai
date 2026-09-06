import json
import logging
import uuid

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
    else:
        security_logger.warning(message)


def audit_acl_change(
    *,
    action: str,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    target_user_id: uuid.UUID,
    resource_type: str,
    resource_id: str,
    access: str,
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
