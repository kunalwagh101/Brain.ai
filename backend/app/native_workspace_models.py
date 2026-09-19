import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


def _enum_values(enum_type):
    return [item.value for item in enum_type]


class NativeTeamStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class NativeTeam(Base):
    __tablename__ = "native_teams"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "slug",
            name="uq_native_team_org_slug",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_native_team_org_id",
        ),
        CheckConstraint("revision >= 1", name="ck_native_team_revision_positive"),
        Index(
            "ix_native_team_org_status_name",
            "organization_id",
            "status",
            "name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(96), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[NativeTeamStatus] = mapped_column(
        Enum(
            NativeTeamStatus,
            native_enum=False,
            length=24,
            values_callable=_enum_values,
        ),
        default=NativeTeamStatus.ACTIVE,
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class NativeChannelGroup(Base):
    __tablename__ = "native_channel_groups"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "team_id"],
            ["native_teams.organization_id", "native_teams.id"],
            name="fk_native_channel_group_team_scope",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "organization_id",
            "team_id",
            "slug",
            name="uq_native_channel_group_team_slug",
        ),
        UniqueConstraint(
            "organization_id",
            "team_id",
            "id",
            name="uq_native_channel_group_scope_id",
        ),
        CheckConstraint(
            "revision >= 1",
            name="ck_native_channel_group_revision_positive",
        ),
        Index(
            "ix_native_channel_group_org_team_status_name",
            "organization_id",
            "team_id",
            "status",
            "name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    team_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(96), nullable=False)
    status: Mapped[NativeTeamStatus] = mapped_column(
        Enum(
            NativeTeamStatus,
            native_enum=False,
            length=24,
            values_callable=_enum_values,
        ),
        default=NativeTeamStatus.ACTIVE,
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
