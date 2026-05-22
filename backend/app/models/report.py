from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base_class import Base, IDModelMixin, TimestampModelMixin, SoftDeleteModelMixin


class ReportSchedule(Base, IDModelMixin, TimestampModelMixin, SoftDeleteModelMixin):
    """Concrete model representing configurable recurring dashboard report schedules."""
    __tablename__ = "report_schedules"

    organization_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    dashboard_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dashboards.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    frequency: Mapped[str] = mapped_column(String(50), nullable=False)  # daily, weekly, monthly
    recipients: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)  # list of email strings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    dashboard: Mapped[Optional["Dashboard"]] = relationship("Dashboard")
    histories: Mapped[List["ReportHistory"]] = relationship(
        "ReportHistory",
        back_populates="report_schedule",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class ReportHistory(Base, IDModelMixin, TimestampModelMixin, SoftDeleteModelMixin):
    """Concrete model logging actual report evaluation triggers and archives."""
    __tablename__ = "report_histories"

    report_schedule_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("report_schedules.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    organization_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # pending, success, failed
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # path to compiled HTML on disk

    # Relationships
    report_schedule: Mapped["ReportSchedule"] = relationship("ReportSchedule", back_populates="histories")
