import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, IDModelMixin, TimestampModelMixin, SoftDeleteModelMixin


class Invitation(Base, IDModelMixin, TimestampModelMixin, SoftDeleteModelMixin):
    """Model tracking pending team workspace onboarding invites."""
    
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    inviter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="viewer"
    )
    token: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_accepted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
