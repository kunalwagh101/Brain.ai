import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class SearchDocument(Base):
    __tablename__ = "search_documents"
    __table_args__ = (
        UniqueConstraint(
            "canonical_event_id",
            name="uq_search_document_canonical_event",
        ),
        Index(
            "ix_search_documents_org_provider",
            "organization_id",
            "source_provider",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    canonical_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canonical_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_provider: Mapped[str] = mapped_column(String(40), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
