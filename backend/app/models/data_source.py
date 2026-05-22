import uuid
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, IDModelMixin, TimestampModelMixin, SoftDeleteModelMixin


class DataSource(Base, IDModelMixin, TimestampModelMixin, SoftDeleteModelMixin):
    """Model representing dynamic user data ingestion sources."""

    __tablename__ = "data_sources"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="api"  # "api", "csv", "webhook"
    )
    config: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(foreign_keys=[organization_id])
