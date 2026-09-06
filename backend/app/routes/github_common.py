import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.github import GitHubAPIError, GitHubConfigurationError, GitHubTransportError
from app.integrations import connection_can_sync
from app.models import IntegrationConnection, IntegrationStatus
from app.permissions import Permission, require_organization_permission

manage_integrations = require_organization_permission(Permission.INTEGRATION_MANAGE)


def github_failure(exc: Exception) -> HTTPException:
    if isinstance(exc, GitHubConfigurationError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub integration is not configured",
        )
    if isinstance(exc, GitHubAPIError):
        response_status = (
            status.HTTP_400_BAD_REQUEST
            if 400 <= exc.status_code < 500
            else status.HTTP_502_BAD_GATEWAY
        )
        return HTTPException(
            status_code=response_status,
            detail=f"GitHub API request failed: {exc.code}",
        )
    if isinstance(exc, GitHubTransportError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub is temporarily unavailable",
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="GitHub integration failed",
    )


def get_github_connection(
    db: Session,
    *,
    organization_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> IntegrationConnection:
    connection = db.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.id == connection_id,
            IntegrationConnection.organization_id == organization_id,
            IntegrationConnection.provider == "github",
        )
    )
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub integration not found",
        )
    if not connection_can_sync(connection):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="GitHub integration is not active",
        )
    return connection


def active_github_installations(
    db: Session,
    installation_id: int,
) -> list[IntegrationConnection]:
    return list(
        db.scalars(
            select(IntegrationConnection).where(
                IntegrationConnection.provider == "github",
                IntegrationConnection.external_account_id == str(installation_id),
                IntegrationConnection.status == IntegrationStatus.ACTIVE,
            )
        )
    )


GitHubManageDependency = Annotated[object, Depends(manage_integrations)]
