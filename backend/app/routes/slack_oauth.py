import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import IntegrationConnection, IntegrationHealth, IntegrationStatus, User
from app.permissions import (
    AuthorizationContext,
    Permission,
    authorize_organization,
    require_organization_permission,
)
from app.routes.slack_common import slack_failure
from app.schemas import IntegrationConnectionRead, SlackInstallRead
from app.secrets import SecretStore, SecretStoreError, get_secret_store
from app.slack import (
    SLACK_OAUTH_SCOPES,
    SlackAPIClient,
    SlackAPIError,
    SlackConfigurationError,
    SlackTransportError,
    create_oauth_state,
    get_slack_api_client,
    verify_oauth_state,
)

router = APIRouter(tags=["slack"])
logger = logging.getLogger("brain.slack")
_manage_integrations = require_organization_permission(Permission.INTEGRATION_MANAGE)


def _parse_installation(
    installation: dict[str, object],
) -> tuple[str, str, str, set[str]]:
    team = installation.get("team")
    token = installation.get("access_token")
    scope_value = installation.get("scope")
    if not isinstance(team, dict) or not isinstance(token, str) or not token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Slack returned invalid OAuth data",
        )
    team_id = team.get("id")
    team_name = team.get("name")
    if not isinstance(team_id, str) or not team_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Slack returned no workspace ID",
        )
    if not isinstance(team_name, str) or not team_name:
        team_name = team_id
    granted_scopes = (
        {item.strip() for item in scope_value.split(",") if item.strip()}
        if isinstance(scope_value, str)
        else set()
    )
    if set(SLACK_OAUTH_SCOPES) - granted_scopes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slack did not grant all required scopes",
        )
    return team_id, team_name, token, granted_scopes


@router.get(
    "/organizations/{organization_id}/integrations/slack/install",
    response_model=SlackInstallRead,
)
def slack_install(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_manage_integrations)],
    settings: Annotated[Settings, Depends(get_settings)],
    slack_api: Annotated[SlackAPIClient, Depends(get_slack_api_client)],
) -> SlackInstallRead:
    state_value = create_oauth_state(
        organization_id=organization_id,
        user_id=authorization.user_id,
        secret=settings.app_secret,
    )
    try:
        authorization_url = slack_api.build_authorization_url(state_value)
    except SlackConfigurationError as exc:
        raise slack_failure(exc) from exc
    return SlackInstallRead(
        authorization_url=authorization_url,
        scopes=list(SLACK_OAUTH_SCOPES),
    )


@router.get(
    "/integrations/slack/oauth/callback",
    response_model=IntegrationConnectionRead,
)
def slack_oauth_callback(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    store: Annotated[SecretStore, Depends(get_secret_store)],
    slack_api: Annotated[SlackAPIClient, Depends(get_slack_api_client)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> IntegrationConnection:
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slack authorization denied",
        )
    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Slack OAuth callback",
        )
    try:
        organization_id, user_id = verify_oauth_state(
            state,
            secret=settings.app_secret,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
    authorization = authorize_organization(
        db=db,
        organization_id=organization_id,
        user=user,
        permission=Permission.INTEGRATION_MANAGE,
    )

    try:
        installation = slack_api.exchange_code(code)
    except (SlackAPIError, SlackTransportError, SlackConfigurationError) as exc:
        raise slack_failure(exc) from exc
    team_id, team_name, token, granted_scopes = _parse_installation(installation)

    connections = list(
        db.scalars(
            select(IntegrationConnection).where(
                IntegrationConnection.provider == "slack",
                IntegrationConnection.external_account_id == team_id,
            )
        )
    )
    for existing in connections:
        if (
            existing.organization_id != organization_id
            and existing.status != IntegrationStatus.REVOKED
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Slack workspace is already connected to another organization",
            )

    connection = next(
        (item for item in connections if item.organization_id == organization_id),
        None,
    )
    if connection is not None and connection.status == IntegrationStatus.REVOKE_FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete the failed revocation before reconnecting Slack",
        )

    try:
        new_secret_ref = store.store_connection_secret(
            organization_id=organization_id,
            connection_id=uuid.uuid4(),
            provider="slack",
            credentials={"bot_token": token},
        )
    except SecretStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack credentials could not be stored",
        ) from exc

    old_secret_ref: str | None = None
    if connection is None:
        connection = IntegrationConnection(
            id=uuid.uuid4(),
            organization_id=organization_id,
            provider="slack",
            external_account_id=team_id,
            display_name=team_name,
            status=IntegrationStatus.ACTIVE,
            health=IntegrationHealth.UNKNOWN,
            scopes=sorted(granted_scopes),
            secret_ref=new_secret_ref,
            created_by_user_id=authorization.user_id,
        )
        db.add(connection)
    else:
        old_secret_ref = connection.secret_ref
        connection.display_name = team_name
        connection.status = IntegrationStatus.ACTIVE
        connection.health = IntegrationHealth.UNKNOWN
        connection.scopes = sorted(granted_scopes)
        connection.secret_ref = new_secret_ref
        connection.revoked_at = None
        connection.last_error_code = None

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        try:
            store.schedule_delete(new_secret_ref)
        except SecretStoreError:
            logger.exception("Failed to retire Slack secret after database failure")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack connection could not be persisted",
        ) from exc
    db.refresh(connection)

    if old_secret_ref and old_secret_ref != new_secret_ref:
        try:
            store.schedule_delete(old_secret_ref)
        except SecretStoreError:
            connection.health = IntegrationHealth.DEGRADED
            connection.last_error_code = "old_secret_retirement_failed"
            db.commit()
            db.refresh(connection)
    return connection
