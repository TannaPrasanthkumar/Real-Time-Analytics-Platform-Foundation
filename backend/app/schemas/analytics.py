from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class TimeInterval(str, Enum):
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class MetricType(str, Enum):
    PAGE_VIEWS = "page_views"
    UNIQUE_VISITORS = "unique_visitors"
    BOUNCE_RATE = "bounce_rate"
    AVG_SESSION_DURATION = "avg_session_duration"


class MetricOverview(BaseModel):
    """SaaS metrics aggregate overview schema with period-over-period (PoP) differences."""

    page_views: int = Field(..., description="Total count of page views in the period.")
    unique_visitors: int = Field(..., description="Unique visitors/DAUs in the period.")
    bounce_rate: float = Field(..., description="Bounce rate percentage in the period.")
    avg_session_duration: float = Field(..., description="Average session duration in seconds.")

    # Deltas compared to the prior period of the same length (e.g. +15.5%)
    page_views_change: float | None = Field(default=None, description="Percentage change in page views.")
    unique_visitors_change: float | None = Field(default=None, description="Percentage change in unique visitors.")
    bounce_rate_change: float | None = Field(default=None, description="Percentage change in bounce rate.")
    avg_session_duration_change: float | None = Field(default=None, description="Percentage change in avg session duration.")


class TimeseriesPoint(BaseModel):
    """Single coordinate point in an analytical metric chart."""

    bucket: datetime = Field(..., description="Truncated time bucket start timestamp.")
    value: float = Field(..., description="Aggregate metric value within the bucket.")
    moving_average: float | None = Field(default=None, description="Rolling moving average value.")


class TimeseriesResponse(BaseModel):
    """Analytical time-series query output."""

    metric: MetricType
    interval: TimeInterval
    points: list[TimeseriesPoint]


class BreakdownItem(BaseModel):
    """Aggregate metric categorization bucket."""

    label: str = Field(..., description="Extracted category label (e.g. 'Chrome', '/pricing').")
    count: int = Field(..., description="Total occurrences inside the category.")
    percentage: float = Field(..., description="Percentage slice of the property totals.")


class BreakdownResponse(BaseModel):
    """Event property segmentation breakdown."""

    property_key: str
    items: list[BreakdownItem]
