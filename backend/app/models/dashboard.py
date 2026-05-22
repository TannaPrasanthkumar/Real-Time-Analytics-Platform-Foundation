from typing import List, Optional
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base_class import Base, IDModelMixin, TimestampModelMixin, SoftDeleteModelMixin


class Dashboard(Base, IDModelMixin, TimestampModelMixin, SoftDeleteModelMixin):
    """Concrete model representing customizable metrics visualization dashboards."""
    __tablename__ = "dashboards"

    organization_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    share_token: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )

    # Relationships
    widgets: Mapped[List["Widget"]] = relationship(
        "Widget",
        back_populates="dashboard",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class Widget(Base, IDModelMixin, TimestampModelMixin, SoftDeleteModelMixin):
    """Concrete model representing customized individual metric widgets."""
    __tablename__ = "widgets"

    dashboard_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dashboards.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    type: Mapped[str] = mapped_column(
        String(50), nullable=False  # line, bar, pie, kpi, table
    )
    layout: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict  # e.g., {"x": 0, "y": 0, "w": 6, "h": 4}
    )
    query_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict  # e.g., {"metric_type": "page_views", "interval": "day"}
    )

    # Relationships
    dashboard: Mapped["Dashboard"] = relationship(
        "Dashboard",
        back_populates="widgets"
    )
