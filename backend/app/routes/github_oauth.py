import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.github import (
    GitHubAPIClient,
    GitHubAPIError,
    GitHubConfigurationError,
    GitHubTransportError,
    create_install_state,
    create_selection_token,
    get_github_api_client,
    verify_install_state,
    verify_selection_token,
)
from app.models import IntegrationConnection, IntegrationHealth, IntegrationStatus, User
from app.permissions import AuthorizationContext, Permission, authorize_organization
from app.routes.github_common import active_github_installations, github_failure, manage_integrations
from app.schemas import (
    GitHubConnectRequest,
    GitHubInstallationCandidate,
    GitHubInstallRead,
    GitHubOAuthCallbackRead,
    IntegrationConnectionRead,
)

router = APIRouter(tags=["github"])


@router.get(
    "/organizations/{organization_id}/integrations/github/install",
    response_model=GitHubInstallRead,
)
def github_install(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(manage_integrations)],
    settings: Annotated[Settings, Depends(get_settings)],
    github_api: Annotated[GitHubAPIClient, Depends(get_github_api_client)],
) -> GitHubInstallRead:
    state_value = create_install_state(
        organization_id=organization_id,
        user_id=authorization.user_id,
        secret=settings.app_secret,
    )
    try:
        url = github_api.installation_url(state_value)
    except GitHubConfigurationError as exc:
        raise github_failure(exc) from exc
    return GitHubInstallRead(installation_url=url)


@router.get(
    "/integrations/github/oauth/callback",
    response_model=GitHubOAuthCallbackRead,
)
def github_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
    github_api: Annotated[GitHubAPIClient, Depends(get_github_api_client)] = None,
) -> GitHubOAuthCallbackRead:
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub authorization denied",
        )
    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GitHub OAuth callback",
        )
    assert settings is not None and db is not None and github_api is not None
    try:
        organization_id, user_id = verify_install_state(
            state,
            secret=settings.app_secret,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    authorize_organization(
        db=db,
        organization_id=organization_id,
        user=user,
        permission=Permission.INTEGRATION_MANAGE,
    )

    try:
        user_token = github_api.exchange_user_code(code)
        installations = github_api.list_user_installations(user_token)
    except (GitHubAPIError, GitHubTransportError, GitHubConfigurationError) as exc:
        raise github_failure(exc) from exc

    candidates: list[GitHubInstallationCandidate] = []
    for installation in installations:
        if str(installation.get("app_id")) != str(settings.github_app_id):
            continue
        account = installation.get("account")
        installation_id = installation.get("id")
        if not isinstance(account, dict) or not isinstance(installation_id, int):
            continue
        account_login = account.get("login")
        if not isinstance(account_login, str) or not account_login:
            continue
        try:
            selection_token = create_selection_token(
                organization_id=organization_id,
                user_id=user_id,
                installation=installation,
                secret=settings.app_secret,
            )
        except ValueError:
            continue
        candidates.append(
            GitHubInstallationCandidate(
                installation_id=installation_id,
                account_login=account_login,
                target_type=str(installation.get("target_type") or "Unknown"),
                repository_selection=str(
                    installation.get("repository_selection") or "selected"
                ),
                selection_token=selection_token,
            )
        )
    return GitHubOAuthCallbackRead(installations=candidates)


@router.post(
    "/organizations/{organization_id}/integrations/github/connect",
    response_model=IntegrationConnectionRead,
    status_code=status.HTTP_201_CREATED,
)
def connect_github_installation(
    organization_id: uuid.UUID,
    payload: GitHubConnectRequest,
    authorization: Annotated[AuthorizationContext, Depends(manage_integrations)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    github_api: Annotated[GitHubAPIClient, Depends(get_github_api_client)],
) -> IntegrationConnection:
    try:
        selection = verify_selection_token(payload.selection_token, secret=settings.app_secret)
        token_organization_id = uuid.UUID(str(selection["organization_id"]))
        token_user_id = uuid.UUID(str(selection["user_id"]))
        installation_id = int(selection["installation_id"])
        account_id = int(selection["account_id"])
        account_login = str(selection["account_login"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GitHub installation selection",
        ) from exc
    if token_organization_id != organization_id or token_user_id != authorization.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    try:
        verified = github_api.get_app_installation(installation_id)
    except (GitHubAPIError, GitHubTransportError, GitHubConfigurationError) as exc:
        raise github_failure(exc) from exc
    verified_account = verified.get("account")
    if not isinstance(verified_account, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub returned invalid installation data",
        )
    if (
        verified.get("id") != installation_id
        or verified_account.get("id") != account_id
        or verified_account.get("login") != account_login
        or str(verified.get("app_id")) != str(settings.github_app_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="GitHub installation verification changed",
        )

    existing = active_github_installations(db, installation_id)
    if existing:
        if any(item.organization_id != organization_id for item in existing):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="GitHub installation is already connected to another organization",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="GitHub installation is already connected",
        )

    permissions = verified.get("permissions")
    events = verified.get("events")
    scopes: list[str] = []
    if isinstance(permissions, dict):
        scopes.extend(
            f"permission:{key}:{value}"
            for key, value in sorted(permissions.items())
            if isinstance(key, str) and isinstance(value, str)
        )
    if isinstance(events, list):
        scopes.extend(f"event:{item}" for item in events if isinstance(item, str))

    connection = IntegrationConnection(
        organization_id=organization_id,
        provider="github",
        external_account_id=str(installation_id),
        display_name=account_login[:160],
        status=IntegrationStatus.ACTIVE,
        health=IntegrationHealth.UNKNOWN,
        scopes=scopes,
        provider_metadata={
            "account_id": account_id,
            "account_login": account_login,
            "target_type": str(verified.get("target_type") or "Unknown"),
            "repository_selection": str(
                verified.get("repository_selection") or "selected"
            ),
        },
        secret_ref=None,
        created_by_user_id=authorization.user_id,
    )
    db.add(connection)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="GitHub installation is already connected",
        ) from None
    db.refresh(connection)
    return connection
