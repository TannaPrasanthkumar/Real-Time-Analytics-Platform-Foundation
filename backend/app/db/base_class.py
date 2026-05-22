import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import DateTime, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models.
    
    Dynamically generates the database __tablename__ from the model class name.
    """
    id: Any
    __name__: str

    # Automatically generate __tablename__ based on the model class name
    @declared_attr
    @classmethod
    def __tablename__(cls) -> str:
        # Converts class names like "UserAuth" into a plural snake_case table "user_auths"
        name = cls.__name__.lower()
        if name.endswith("y"):
            return f"{name[:-1]}ies"
        elif name.endswith("s"):
            return f"{name}es"
        return f"{name}s"


class IDModelMixin:
    """Mixin to inject standard UUID primary keys into data models."""
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        sort_order=-10,  # Forces primary key column to appear first in DB schemas
    )


class TimestampModelMixin:
    """Mixin to inject timezone-aware creation and update audits into models."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        sort_order=90,  # Pushes audits to the bottom of the table
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        sort_order=91,
    )


class SoftDeleteModelMixin:
    """Mixin to inject soft-deletion parameters for transactional records."""

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,  # Indexed to speed up default "is_deleted = False" query prunings
        sort_order=92,
    )
    
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
        nullable=True,
        sort_order=93,
    )

    def trigger_soft_delete(self) -> None:
        """Helper to transition record to a soft-deleted state."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
