import uuid
from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.evidence_ingestion import (
    MAX_EVIDENCE_BYTES,
    EvidenceConflictError,
    EvidenceIngestionError,
    delete_evidence_source,
    get_visible_evidence_source,
    ingest_evidence,
)
from app.evidence_models import (
    EvidenceKind,
    EvidenceSource,
    EvidenceSourceStatus,
    EvidenceVisibility,
)
from app.evidence_workspace import (
    can_delete_evidence_source,
    list_visible_evidence_sources_page,
)
from app.models import IntegrationConnection, IntegrationStatus
from app.permissions import AuthorizationContext, Permission, require_organization_permission

router = APIRouter(
    prefix="/organizations/{organization_id}/evidence",
    tags=["evidence"],
)
_read = require_organization_permission(Permission.RESOURCE_READ)
_write = require_organization_permission(Permission.RESOURCE_WRITE)


class EvidenceSourceRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    integration_connection_id: uuid.UUID
    kind: EvidenceKind
    title: str
    filename: str
    media_type: str
    content_sha256: str
    byte_size: int
    source_visibility: EvidenceVisibility
    chunk_count: int
    extracted_char_count: int
    created_by_user_id: uuid.UUID
    occurred_at: datetime | None
    status: EvidenceSourceStatus
    integration_status: IntegrationStatus
    retrieval_available: bool
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    can_delete: bool

    model_config = {"from_attributes": True}


def _request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else None


def _raise_evidence_error(exc: EvidenceIngestionError) -> None:
    if isinstance(exc, EvidenceConflictError):
        code = status.HTTP_409_CONFLICT
    elif exc.code == "evidence_not_found":
        code = status.HTTP_404_NOT_FOUND
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(
        status_code=code,
        detail={"code": exc.code, "message": str(exc)},
    ) from exc


def _integration_statuses(
    db: Session,
    sources: list[EvidenceSource],
) -> dict[uuid.UUID, IntegrationStatus]:
    connection_ids = {source.integration_connection_id for source in sources}
    if not connection_ids:
        return {}
    return {
        connection_id: connection_status
        for connection_id, connection_status in db.execute(
            select(IntegrationConnection.id, IntegrationConnection.status).where(
                IntegrationConnection.id.in_(connection_ids)
            )
        ).all()
    }


def _read_source(
    source: EvidenceSource,
    authorization: AuthorizationContext,
    integration_status: IntegrationStatus,
) -> EvidenceSourceRead:
    return EvidenceSourceRead(
        id=source.id,
        organization_id=source.organization_id,
        integration_connection_id=source.integration_connection_id,
        kind=source.kind,
        title=source.title,
        filename=source.filename,
        media_type=source.media_type,
        content_sha256=source.content_sha256,
        byte_size=source.byte_size,
        source_visibility=source.source_visibility,
        chunk_count=source.chunk_count,
        extracted_char_count=source.extracted_char_count,
        created_by_user_id=source.created_by_user_id,
        occurred_at=source.occurred_at,
        status=source.status,
        integration_status=integration_status,
        retrieval_available=(
            source.status == EvidenceSourceStatus.ACTIVE
            and integration_status == IntegrationStatus.ACTIVE
        ),
        last_error_code=source.last_error_code,
        created_at=source.created_at,
        updated_at=source.updated_at,
        deleted_at=source.deleted_at,
        can_delete=can_delete_evidence_source(
            source,
            actor_user_id=authorization.user_id,
            actor_role=authorization.role,
        ),
    )


def _read_one(
    db: Session,
    source: EvidenceSource,
    authorization: AuthorizationContext,
) -> EvidenceSourceRead:
    statuses = _integration_statuses(db, [source])
    integration_status = statuses.get(source.integration_connection_id)
    if integration_status is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evidence integration state is unavailable",
        )
    return _read_source(source, authorization, integration_status)


@router.post("/uploads", response_model=EvidenceSourceRead, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    organization_id: uuid.UUID,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
    kind: Annotated[EvidenceKind, Form()] = EvidenceKind.DOCUMENT,
    title: Annotated[str | None, Form(max_length=512)] = None,
    visibility: Annotated[EvidenceVisibility, Form()] = EvidenceVisibility.ORGANIZATION,
    occurred_at: Annotated[datetime | None, Form()] = None,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", max_length=128),
    ] = None,
) -> EvidenceSourceRead:
    content = await file.read(MAX_EVIDENCE_BYTES + 1)
    if len(content) > MAX_EVIDENCE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "upload_too_large", "message": "Evidence upload exceeds 10 MB"},
        )
    try:
        source = ingest_evidence(
            db,
            organization_id=organization_id,
            actor_user_id=authorization.user_id,
            kind=kind,
            title=title,
            filename=file.filename or "upload",
            media_type=file.content_type or "application/octet-stream",
            content=content,
            visibility=visibility,
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
            request_id=_request_id(request),
        )
        return _read_one(db, source, authorization)
    except EvidenceIngestionError as exc:
        _raise_evidence_error(exc)


@router.get("", response_model=list[EvidenceSourceRead])
def list_evidence(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    evidence_status: EvidenceSourceStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[EvidenceSourceRead]:
    sources = list_visible_evidence_sources_page(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        status=evidence_status,
        limit=limit,
    )
    statuses = _integration_statuses(db, sources)
    return [
        _read_source(source, authorization, statuses[source.integration_connection_id])
        for source in sources
        if source.integration_connection_id in statuses
    ]


@router.get("/{source_id}", response_model=EvidenceSourceRead)
def read_evidence(
    organization_id: uuid.UUID,
    source_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> EvidenceSourceRead:
    source = get_visible_evidence_source(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        source_id=source_id,
    )
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence source not found",
        )
    return _read_one(db, source, authorization)


@router.delete("/{source_id}", response_model=EvidenceSourceRead)
def delete_evidence(
    organization_id: uuid.UUID,
    source_id: uuid.UUID,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> EvidenceSourceRead:
    try:
        source = delete_evidence_source(
            db,
            organization_id=organization_id,
            actor_user_id=authorization.user_id,
            actor_role=authorization.role,
            source_id=source_id,
            request_id=_request_id(request),
        )
        return _read_one(db, source, authorization)
    except EvidenceIngestionError as exc:
        _raise_evidence_error(exc)
