from typing import List, TYPE_CHECKING
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, IDModelMixin, TimestampModelMixin, SoftDeleteModelMixin

if TYPE_CHECKING:
    from app.models.user import UserOrganization


class Organization(Base, IDModelMixin, TimestampModelMixin, SoftDeleteModelMixin):
    """Concrete model representing logical multi-tenant work environments."""
    
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    slug: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # Relationships
    memberships: Mapped[List["UserOrganization"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
