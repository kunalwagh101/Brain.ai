import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai_gateway import AIGatewayError, AIInvocationError
from app.ask_brain import AskBrainError, AskBrainResult, ask_company_question
from app.database import get_db
from app.embeddings import EmbeddingError, build_embedding_client
from app.permissions import (
    AuthorizationContext,
    Permission,
    require_organization_permission,
)
from app.search import SearchMode
from app.secrets import SecretStore, get_secret_store

router = APIRouter(
    prefix="/organizations/{organization_id}/ask-brain",
    tags=["ask-brain"],
)
_use_ai = require_organization_permission(Permission.AI_USE)


class AskBrainRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    provider_configuration_id: uuid.UUID
    model_configuration_id: uuid.UUID
    search_mode: SearchMode = SearchMode.HYBRID
    search_limit: int = Field(default=8, ge=1, le=8)
    max_output_tokens: int | None = Field(default=None, ge=1, le=1_000_000)
    attribution_node_id: uuid.UUID | None = None


class AskBrainClaimRead(BaseModel):
    text: str
    citation_ids: list[str]


class AskBrainCitationRead(BaseModel):
    evidence_id: str
    document_id: uuid.UUID
    canonical_event_id: uuid.UUID
    source_provider: str
    source_event_id: str | None
    object_type: str
    object_external_id: str
    title: str
    excerpt: str
    occurred_at: datetime | None
    provenance: dict[str, object]


class AskBrainResponse(BaseModel):
    status: str
    answer: str | None
    claims: list[AskBrainClaimRead]
    citations: list[AskBrainCitationRead]
    uncertainty: str | None
    ai_request_id: uuid.UUID | None
    semantic_status: str


def _gateway_error(exc: AIGatewayError) -> None:
    message = str(exc)
    if "not found" in message:
        code = status.HTTP_404_NOT_FOUND
    elif message == "AI budget exhausted":
        code = status.HTTP_429_TOO_MANY_REQUESTS
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=message) from exc


def _response(result: AskBrainResult) -> AskBrainResponse:
    return AskBrainResponse(
        status=result.status,
        answer=result.answer,
        claims=[
            AskBrainClaimRead(text=claim.text, citation_ids=list(claim.citation_ids))
            for claim in result.claims
        ],
        citations=[
            AskBrainCitationRead(
                evidence_id=citation.evidence_id,
                document_id=citation.document_id,
                canonical_event_id=citation.canonical_event_id,
                source_provider=citation.source_provider,
                source_event_id=citation.source_event_id,
                object_type=citation.object_type,
                object_external_id=citation.object_external_id,
                title=citation.title,
                excerpt=citation.excerpt,
                occurred_at=citation.occurred_at,
                provenance=citation.provenance,
            )
            for citation in result.citations
        ],
        uncertainty=result.uncertainty,
        ai_request_id=result.ai_request_id,
        semantic_status=result.semantic_status,
    )


@router.post("", response_model=AskBrainResponse)
def ask_brain(
    organization_id: uuid.UUID,
    payload: AskBrainRequest,
    authorization: Annotated[AuthorizationContext, Depends(_use_ai)],
    db: Annotated[Session, Depends(get_db)],
    secret_store: Annotated[SecretStore, Depends(get_secret_store)],
) -> AskBrainResponse:
    try:
        embedding_client, embedding_model = build_embedding_client()
    except EmbeddingError:
        embedding_client, embedding_model = None, None

    try:
        result = ask_company_question(
            db,
            secret_store=secret_store,
            organization_id=organization_id,
            user_id=authorization.user_id,
            role=authorization.role,
            provider_configuration_id=payload.provider_configuration_id,
            model_configuration_id=payload.model_configuration_id,
            question=payload.question,
            search_mode=payload.search_mode,
            search_limit=payload.search_limit,
            embedding_client=embedding_client,
            embedding_model=embedding_model,
            attribution_node_id=payload.attribution_node_id,
            max_output_tokens=payload.max_output_tokens,
        )
    except AIGatewayError as exc:
        _gateway_error(exc)
    except AIInvocationError as exc:
        code = (
            status.HTTP_429_TOO_MANY_REQUESTS
            if exc.code == "rate_limited"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        raise HTTPException(
            status_code=code,
            detail={"code": exc.code, "request_id": str(exc.request_id)},
        ) from exc
    except AskBrainError as exc:
        client_error = exc.code in {"question_required", "question_too_long"}
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
                if client_error
                else status.HTTP_502_BAD_GATEWAY
            ),
            detail={
                "code": exc.code,
                "request_id": str(exc.request_id) if exc.request_id else None,
            },
        ) from exc
    return _response(result)
