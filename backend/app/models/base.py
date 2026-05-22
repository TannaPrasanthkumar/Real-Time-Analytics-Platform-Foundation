# ==============================================================================
# Unified Database Model Registry File
# ==============================================================================
# This module imports all model definitions into a single namespace.
# It serves as the primary metadata source for Alembic autogeneration.
# ==============================================================================

# Import core declarative base and mixins
from app.db.base_class import Base, IDModelMixin, TimestampModelMixin, SoftDeleteModelMixin

# Import concrete models for Phase 2 & 3
from app.models.user import User, UserOrganization
from app.models.organization import Organization
from app.models.invitation import Invitation
from app.models.api_key import APIKey
from app.models.data_source import DataSource
from app.models.event import Event
from app.models.dashboard import Dashboard, Widget
from app.models.alert import AlertRule, AlertHistory
from app.models.report import ReportSchedule, ReportHistory


# Expose model metadata for Alembic env.py target_metadata binding
metadata = Base.metadata


