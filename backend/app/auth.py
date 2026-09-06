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


def verify_access_token(token: str) -> AuthPrincipal:
    settings = get_settings()
    audience = settings.auth_audience
    if not settings.workos_client_id or not audience:
        raise RuntimeError("WorkOS authentication is not configured")

    signing_key = get_jwks_client().get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=audience,
        issuer=settings.workos_issuer,
        options={"require": ["exp", "sub", "iss", "aud"]},
    )

    actor = claims.get("act")
    email = actor.get("sub") if isinstance(actor, dict) else None
    if not isinstance(email, str) or "@" not in email:
        raise InvalidTokenError("Verified token does not contain a usable user email")

    permissions = claims.get("permissions")
    if not isinstance(permissions, list) or not all(isinstance(item, str) for item in permissions):
        permissions = []

    org_id = claims.get("org_id")
    role = claims.get("role")
    return AuthPrincipal(
        subject=str(claims["sub"]),
        email=email.strip().lower(),
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
