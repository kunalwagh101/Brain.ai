from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWKClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import ExternalIdentity, User

_bearer = HTTPBearer(auto_error=False)
_WORKOS_EMAIL_CLAIM = "urn:brain:user_email"


@dataclass(frozen=True, slots=True)
class AuthPrincipal:
    subject: str
    email: str
    provider_organization_id: str | None
    provider_role: str | None
    permissions: tuple[str, ...]


@lru_cache
def get_jwks_client() -> PyJWKClient:
    client_id = get_settings().workos_client_id
    if not client_id:
        raise RuntimeError("WorkOS authentication is not configured")
    return PyJWKClient(f"https://api.workos.com/sso/jwks/{client_id}")


def _claim_matches(value: object, expected: str) -> bool:
    if isinstance(value, str):
        return value == expected
    if isinstance(value, list):
        return expected in value and all(isinstance(item, str) for item in value)
    return False


def _validate_workos_application_claims(claims: dict[str, object]) -> None:
    settings = get_settings()
    client_id = settings.workos_client_id
    if not client_id:
        raise RuntimeError("WorkOS authentication is not configured")

    token_client_id = claims.get("client_id")
    token_audience = claims.get("aud")

    # Current AuthKit session tokens identify the application with `client_id`.
    # Keep compatibility with older/custom JWTs that identify it through `aud`,
    # but never accept a token that is not bound to this configured application.
    if isinstance(token_client_id, str):
        if token_client_id != client_id:
            raise InvalidTokenError("Access token client_id does not match this application")
    elif not _claim_matches(token_audience, client_id):
        raise InvalidTokenError("Access token is not bound to this WorkOS application")

    # `BRAIN_WORKOS_AUDIENCE` is an optional additional custom-audience gate.
    # Standard AuthKit session tokens do not need it; if an operator configures
    # it, the token must carry a matching aud claim in addition to client_id.
    expected_audience = (settings.workos_audience or "").strip()
    if expected_audience and not _claim_matches(token_audience, expected_audience):
        raise InvalidTokenError("Access token audience does not match configured audience")


def _workos_subject_email(claims: dict[str, object]) -> str:
    # Brain deliberately does not use `act.sub` as the user's email. `act`
    # represents actor/delegation context and may identify an impersonator.
    # Configure WorkOS AuthKit's JWT Template with:
    # {"urn:brain:user_email": {{ user.email }}}
    value = claims.get(_WORKOS_EMAIL_CLAIM)
    if not isinstance(value, str):
        raise InvalidTokenError(
            f"Verified token is missing required {_WORKOS_EMAIL_CLAIM} claim"
        )
    email = value.strip().lower()
    if "@" not in email or len(email) > 320:
        raise InvalidTokenError("Verified token contains an invalid Brain user email claim")
    return email


def verify_access_token(token: str) -> AuthPrincipal:
    settings = get_settings()
    if not settings.workos_client_id:
        raise RuntimeError("WorkOS authentication is not configured")

    signing_key = get_jwks_client().get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=settings.workos_issuer,
        options={
            "require": ["exp", "sub", "iss"],
            # AuthKit session tokens use `client_id`; custom/legacy `aud` is
            # validated explicitly below so both forms remain fail-closed.
            "verify_aud": False,
        },
    )
    _validate_workos_application_claims(claims)
    email = _workos_subject_email(claims)

    permissions = claims.get("permissions")
    if not isinstance(permissions, list) or not all(isinstance(item, str) for item in permissions):
        permissions = []

    org_id = claims.get("org_id")
    role = claims.get("role")
    return AuthPrincipal(
        subject=str(claims["sub"]),
        email=email,
        provider_organization_id=org_id if isinstance(org_id, str) else None,
        provider_role=role if isinstance(role, str) else None,
        permissions=tuple(permissions),
    )


def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    try:
        return verify_access_token(credentials.credentials)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is not configured",
        ) from exc
    except (InvalidTokenError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        ) from None
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication verification is temporarily unavailable",
        ) from exc


def get_current_user(
    principal: Annotated[AuthPrincipal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    identity = db.scalar(
        select(ExternalIdentity).where(
            ExternalIdentity.provider == "workos",
            ExternalIdentity.subject == principal.subject,
        )
    )
    if identity is not None:
        return identity.user

    user = db.scalar(select(User).where(User.email == principal.email))
    if user is None:
        user = User(email=principal.email)
        db.add(user)
        db.flush()

    db.add(ExternalIdentity(user_id=user.id, provider="workos", subject=principal.subject))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        identity = db.scalar(
            select(ExternalIdentity).where(
                ExternalIdentity.provider == "workos",
                ExternalIdentity.subject == principal.subject,
            )
        )
        if identity is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Identity could not be linked safely",
            ) from None
        return identity.user

    db.refresh(user)
    return user
