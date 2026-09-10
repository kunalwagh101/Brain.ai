import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.evidence_ingestion import (
    MAX_EVIDENCE_BYTES,
    EvidenceConflictError,
    EvidenceIngestionError,
    delete_evidence_source,
    get_visible_evidence_source,
    ingest_evidence,
    list_visible_evidence_sources,
)
from app.evidence_models import EvidenceKind, EvidenceSource, EvidenceSourceStatus, EvidenceVisibility
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
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

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
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)] = None,
) -> EvidenceSource:
    content = await file.read(MAX_EVIDENCE_BYTES + 1)
    if len(content) > MAX_EVIDENCE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "upload_too_large", "message": "Evidence upload exceeds 10 MB"},
        )
    try:
        return ingest_evidence(
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
    except EvidenceIngestionError as exc:
        _raise_evidence_error(exc)


@router.get("", response_model=list[EvidenceSourceRead])
def list_evidence(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
    evidence_status: EvidenceSourceStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[EvidenceSource]:
    return list_visible_evidence_sources(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        status=evidence_status,
        limit=limit,
    )


@router.get("/{source_id}", response_model=EvidenceSourceRead)
def read_evidence(
    organization_id: uuid.UUID,
    source_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_read)],
    db: Annotated[Session, Depends(get_db)],
) -> EvidenceSource:
    source = get_visible_evidence_source(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        source_id=source_id,
    )
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence source not found")
    return source


@router.delete("/{source_id}", response_model=EvidenceSourceRead)
def delete_evidence(
    organization_id: uuid.UUID,
    source_id: uuid.UUID,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(_write)],
    db: Annotated[Session, Depends(get_db)],
) -> EvidenceSource:
    try:
        return delete_evidence_source(
            db,
            organization_id=organization_id,
            actor_user_id=authorization.user_id,
            actor_role=authorization.role,
            source_id=source_id,
            request_id=_request_id(request),
        )
    except EvidenceIngestionError as exc:
        _raise_evidence_error(exc)
