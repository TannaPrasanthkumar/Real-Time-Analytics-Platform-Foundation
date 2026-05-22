from datetime import datetime
from typing import Any, Dict, List
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AnalyticsRepository:
    """Repository handling advanced read-only aggregations and analytical operations on partitioned events."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_overview_metrics(
        self, organization_id: uuid.UUID, start: datetime, end: datetime
    ) -> Dict[str, Any]:
        """Fetch SaaS aggregates (page views, visitors, bounce rate, avg session duration) in a single CTE sweep."""
        query = text(
            """
            WITH base_events AS (
                SELECT 
                    event_name,
                    timestamp,
                    payload ->> 'session_id' AS session_id,
                    COALESCE(payload ->> 'user_id', payload ->> 'visitor_id', payload ->> 'anonymous_id') AS visitor_id
                FROM events
                WHERE organization_id = :org_id
                  AND timestamp >= :start AND timestamp <= :end
            ),
            session_stats AS (
                SELECT 
                    session_id,
                    COUNT(*) AS event_count,
                    EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) AS duration_seconds
                FROM base_events
                WHERE session_id IS NOT NULL
                GROUP BY session_id
            ),
            overall_aggregates AS (
                SELECT 
                    COUNT(*) FILTER (WHERE event_name IN ('page_view', 'page.view')) AS page_views,
                    COUNT(DISTINCT visitor_id) AS unique_visitors
                FROM base_events
            ),
            session_aggregates AS (
                SELECT 
                    COUNT(*) AS total_sessions,
                    COUNT(*) FILTER (WHERE event_count = 1) AS bounced_sessions,
                    AVG(duration_seconds) AS avg_duration
                FROM session_stats
            )
            SELECT 
                COALESCE(overall_aggregates.page_views, 0) AS page_views,
                COALESCE(overall_aggregates.unique_visitors, 0) AS unique_visitors,
                COALESCE(session_aggregates.total_sessions, 0) AS total_sessions,
                COALESCE(session_aggregates.bounced_sessions, 0) AS bounced_sessions,
                COALESCE(session_aggregates.avg_duration, 0.0) AS avg_duration
            FROM overall_aggregates, session_aggregates;
            """
        )

        res = await self.session.execute(
            query, {"org_id": organization_id, "start": start, "end": end}
        )
        row = res.fetchone()
        if not row:
            return {
                "page_views": 0,
                "unique_visitors": 0,
                "bounce_rate": 0.0,
                "avg_session_duration": 0.0,
            }

        total_sessions = row.total_sessions
        bounced_sessions = row.bounced_sessions
        bounce_rate = (
            (bounced_sessions * 100.0) / total_sessions
            if total_sessions > 0
            else 0.0
        )

        return {
            "page_views": int(row.page_views),
            "unique_visitors": int(row.unique_visitors),
            "bounce_rate": float(bounce_rate),
            "avg_session_duration": float(row.avg_duration or 0.0),
        }

    async def get_timeseries_metrics(
        self,
        organization_id: uuid.UUID,
        start: datetime,
        end: datetime,
        interval: str,
        metric: str,
        moving_average_window: int = 7,
    ) -> List[Dict[str, Any]]:
        """Fetch bucketed metric values with rolling moving averages using window functions."""
        # Sanitize interval to prevent SQL injection (must be standard postgres time groupings)
        valid_intervals = {"minute", "hour", "day", "week", "month"}
        if interval not in valid_intervals:
            raise ValueError(f"Invalid interval parameter: {interval}")

        # Map metric queries
        if metric == "page_views":
            base_select = """
                SELECT 
                    date_trunc(:interval, timestamp) AS bucket,
                    CAST(COUNT(*) FILTER (WHERE event_name IN ('page_view', 'page.view')) AS DOUBLE PRECISION) AS value
                FROM events
                WHERE organization_id = :org_id
                  AND timestamp >= :start AND timestamp <= :end
                GROUP BY bucket
            """
        elif metric == "unique_visitors":
            base_select = """
                SELECT 
                    date_trunc(:interval, timestamp) AS bucket,
                    CAST(COUNT(DISTINCT COALESCE(payload ->> 'user_id', payload ->> 'visitor_id', payload ->> 'anonymous_id')) AS DOUBLE PRECISION) AS value
                FROM events
                WHERE organization_id = :org_id
                  AND timestamp >= :start AND timestamp <= :end
                GROUP BY bucket
            """
        elif metric == "bounce_rate":
            base_select = """
                WITH bucketed_sessions AS (
                    SELECT 
                        date_trunc(:interval, timestamp) AS bucket,
                        payload ->> 'session_id' AS session_id,
                        COUNT(*) AS event_count
                    FROM events
                    WHERE organization_id = :org_id
                      AND timestamp >= :start AND timestamp <= :end
                      AND payload ->> 'session_id' IS NOT NULL
                    GROUP BY bucket, payload ->> 'session_id'
                )
                SELECT 
                    bucket,
                    CAST((COUNT(*) FILTER (WHERE event_count = 1) * 100.0) / NULLIF(COUNT(*), 0) AS DOUBLE PRECISION) AS value
                FROM bucketed_sessions
                GROUP BY bucket
            """
        elif metric == "avg_session_duration":
            base_select = """
                WITH bucketed_session_durations AS (
                    SELECT 
                        date_trunc(:interval, timestamp) AS bucket,
                        payload ->> 'session_id' AS session_id,
                        EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) AS duration_seconds
                    FROM events
                    WHERE organization_id = :org_id
                      AND timestamp >= :start AND timestamp <= :end
                      AND payload ->> 'session_id' IS NOT NULL
                    GROUP BY bucket, payload ->> 'session_id'
                )
                SELECT 
                    bucket,
                    CAST(COALESCE(AVG(duration_seconds), 0.0) AS DOUBLE PRECISION) AS value
                FROM bucketed_session_durations
                GROUP BY bucket
            """
        else:
            raise ValueError(f"Invalid metric parameter: {metric}")

        # Combine into window function wrapper to compute rolling moving average
        full_query = text(
            f"""
            WITH timeseries AS (
                {base_select}
            )
            SELECT 
                bucket,
                COALESCE(value, 0.0) AS value,
                AVG(value) OVER (
                    ORDER BY bucket 
                    ROWS BETWEEN :win PRECEDING AND CURRENT ROW
                ) AS moving_average
            FROM timeseries
            ORDER BY bucket;
            """
        )

        res = await self.session.execute(
            full_query,
            {
                "org_id": organization_id,
                "start": start,
                "end": end,
                "interval": interval,
                "win": max(0, moving_average_window - 1),
            },
        )
        return [
            {
                "bucket": row.bucket,
                "value": float(row.value or 0.0),
                "moving_average": float(row.moving_average or 0.0),
            }
            for row in res.fetchall()
        ]

    async def get_breakdown(
        self,
        organization_id: uuid.UUID,
        start: datetime,
        end: datetime,
        property_key: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Fetch event payload property segmentation breakdown alongside percentage weight."""
        query = text(
            """
            WITH property_counts AS (
                SELECT 
                    COALESCE(payload ->> :prop_key, 'unknown') AS label,
                    COUNT(*) AS count
                FROM events
                WHERE organization_id = :org_id
                  AND timestamp >= :start AND timestamp <= :end
                GROUP BY label
            ),
            total AS (
                SELECT SUM(count) AS total_sum FROM property_counts
            )
            SELECT 
                label,
                count,
                CAST((count * 100.0) / NULLIF(total_sum, 0) AS DOUBLE PRECISION) AS percentage
            FROM property_counts, total
            ORDER BY count DESC
            LIMIT :limit;
            """
        )

        res = await self.session.execute(
            query,
            {
                "org_id": organization_id,
                "start": start,
                "end": end,
                "prop_key": property_key,
                "limit": limit,
            },
        )
        return [
            {
                "label": str(row.label),
                "count": int(row.count),
                "percentage": float(row.percentage or 0.0),
            }
            for row in res.fetchall()
        ]
