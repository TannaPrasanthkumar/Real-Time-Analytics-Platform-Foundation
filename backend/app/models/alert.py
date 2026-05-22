from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, Float, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base_class import Base, IDModelMixin, TimestampModelMixin, SoftDeleteModelMixin


class AlertRule(Base, IDModelMixin, TimestampModelMixin, SoftDeleteModelMixin):
    """Concrete model representing dynamic user-configured metric alert rules."""
    __tablename__ = "alert_rules"

    organization_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Metric threshold parameters
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False)  # error_count, page_views, bounce_rate, error_rate, unique_visitors
    operator: Mapped[str] = mapped_column(String(10), nullable=False)  # >, <, >=, <=, ==
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    time_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    
    # State tracking & snooze thresholds
    current_state: Mapped[str] = mapped_column(String(50), default="Resolved", nullable=False)  # Triggered, Resolved, Muted
    muted_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    snooze_duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    # Destination configuration channel bounds
    slack_webhook: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    email_recipient: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    histories: Mapped[List["AlertHistory"]] = relationship(
        "AlertHistory",
        back_populates="alert_rule",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class AlertHistory(Base, IDModelMixin, TimestampModelMixin, SoftDeleteModelMixin):
    """Concrete model logging alert transitions, history records, and dispatches."""
    __tablename__ = "alert_histories"

    alert_rule_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alert_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    organization_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    state: Mapped[str] = mapped_column(String(50), nullable=False)  # Triggered, Resolved, Muted
    value: Mapped[float] = mapped_column(Float, nullable=False)  # evaluated metric value at state change
    threshold: Mapped[float] = mapped_column(Float, nullable=False)  # configured threshold at state change
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # query logs/metadata

    # Relationships
    alert_rule: Mapped["AlertRule"] = relationship("AlertRule", back_populates="histories")
