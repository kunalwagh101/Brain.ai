import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.evidence_ingestion import evidence_source_visible_to_user
from app.evidence_models import EvidenceSource, EvidenceSourceStatus
from app.models import MembershipRole


def can_delete_evidence_source(
    source: EvidenceSource,
    *,
    actor_user_id: uuid.UUID,
    actor_role: MembershipRole,
) -> bool:
    if source.status == EvidenceSourceStatus.DELETED:
        return False
    return source.created_by_user_id == actor_user_id or actor_role in {
        MembershipRole.OWNER,
        MembershipRole.ADMIN,
    }


def list_visible_evidence_sources_page(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    status: EvidenceSourceStatus | None,
    limit: int,
) -> list[EvidenceSource]:
    """Return up to ``limit`` visible sources without leaking hidden-row counts.

    Evidence visibility currently includes organization-visible sources plus restricted
    sources whose source ACL contains the requesting user. Because source ACL filtering
    is intentionally performed through the canonical Python visibility helper, this
    function uses a bounded keyset scan rather than applying SQL LIMIT before the
    permission check. Hidden rows therefore cannot starve a user's visible page.
    """

    batch_size = min(max(limit * 2, 50), 500)
    visible: list[EvidenceSource] = []
    cursor_created_at: datetime | None = None
    cursor_id: uuid.UUID | None = None

    while len(visible) < limit:
        query = select(EvidenceSource).where(
            EvidenceSource.organization_id == organization_id
        )
        if status is not None:
            query = query.where(EvidenceSource.status == status)
        if cursor_created_at is not None and cursor_id is not None:
            query = query.where(
                or_(
                    EvidenceSource.created_at < cursor_created_at,
                    and_(
                        EvidenceSource.created_at == cursor_created_at,
                        EvidenceSource.id < cursor_id,
                    ),
                )
            )

        batch = list(
            db.scalars(
                query.order_by(
                    EvidenceSource.created_at.desc(),
                    EvidenceSource.id.desc(),
                ).limit(batch_size)
            )
        )
        if not batch:
            break

        visible.extend(
            source
            for source in batch
            if evidence_source_visible_to_user(db, source, user_id)
        )
        if len(batch) < batch_size:
            break

        last = batch[-1]
        cursor_created_at = last.created_at
        cursor_id = last.id

    return visible[:limit]
