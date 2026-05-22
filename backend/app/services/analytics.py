import asyncio
from datetime import datetime
import hashlib
import uuid
from typing import Any, Dict, List
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.analytics import AnalyticsRepository
from app.services.cache import CacheService

logger = structlog.get_logger(__name__)


class AnalyticsService:
    """SaaS Analytics Service layer orchestrating raw queries, Redis caching, and PoP delta calculations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AnalyticsRepository(db)
        self.cache = CacheService()

    def _generate_cache_key(self, org_id: uuid.UUID, endpoint: str, **kwargs) -> str:
        """Create a secure, collision-free deterministic Redis cache key."""
        sorted_keys = sorted(kwargs.items())
        params_str = "&".join(f"{k}={v}" for k, v in sorted_keys)
        hash_digest = hashlib.sha256(params_str.encode()).hexdigest()[:16]
        return f"analytics:{org_id}:{endpoint}:{hash_digest}"

    def _calculate_percentage_change(self, current: float, prior: float) -> float:
        """Safely calculate percentage change between current and prior periods."""
        if prior == 0.0:
            return 100.0 if current > 0.0 else 0.0
        return round(((current - prior) / prior) * 100.0, 2)

    async def get_overview(
        self, organization_id: uuid.UUID, start: datetime, end: datetime, use_cache: bool = True
    ) -> Dict[str, Any]:
        """Fetch metric overview totals along with Period-over-Period (PoP) comparison deltas."""
        # Generate cache key
        cache_key = self._generate_cache_key(
            organization_id, "overview", start=start.isoformat(), end=end.isoformat()
        )

        if use_cache:
            cached_data = await self.cache.get_cached(cache_key)
            if cached_data:
                return cached_data

        # Prior period of equal duration
        duration = end - start
        prior_start = start - duration
        prior_end = start

        logger.info(
            "Fetching analytics overview",
            org_id=organization_id,
            current_range=(start, end),
            prior_range=(prior_start, prior_end),
        )

        # Run both queries in parallel
        current_task = self.repo.get_overview_metrics(organization_id, start, end)
        prior_task = self.repo.get_overview_metrics(organization_id, prior_start, prior_end)
        current_res, prior_res = await asyncio.gather(current_task, prior_task)

        # Calculate percentage changes
        deltas = {
            "page_views_change": self._calculate_percentage_change(
                current_res["page_views"], prior_res["page_views"]
            ),
            "unique_visitors_change": self._calculate_percentage_change(
                current_res["unique_visitors"], prior_res["unique_visitors"]
            ),
            "bounce_rate_change": self._calculate_percentage_change(
                current_res["bounce_rate"], prior_res["bounce_rate"]
            ),
            "avg_session_duration_change": self._calculate_percentage_change(
                current_res["avg_session_duration"], prior_res["avg_session_duration"]
            ),
        }

        response_payload = {**current_res, **deltas}

        # Cache response for 5 minutes (300 seconds)
        await self.cache.set_cached(cache_key, response_payload, ttl=300)

        return response_payload

    async def get_timeseries(
        self,
        organization_id: uuid.UUID,
        start: datetime,
        end: datetime,
        interval: str,
        metric: str,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """Fetch time-series grouped analytical metrics with rolling moving averages."""
        cache_key = self._generate_cache_key(
            organization_id,
            "timeseries",
            start=start.isoformat(),
            end=end.isoformat(),
            interval=interval,
            metric=metric,
        )

        if use_cache:
            cached_data = await self.cache.get_cached(cache_key)
            if cached_data is not None:
                return cached_data

        logger.info(
            "Fetching timeseries metrics",
            org_id=organization_id,
            interval=interval,
            metric=metric,
            range=(start, end),
        )

        points = await self.repo.get_timeseries_metrics(
            organization_id, start, end, interval, metric
        )

        # Cache response for 5 minutes (300 seconds)
        await self.cache.set_cached(cache_key, points, ttl=300)

        return points

    async def get_breakdown(
        self,
        organization_id: uuid.UUID,
        start: datetime,
        end: datetime,
        property_key: str,
        limit: int = 10,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """Fetch payload property breakdown segments."""
        cache_key = self._generate_cache_key(
            organization_id,
            "breakdown",
            start=start.isoformat(),
            end=end.isoformat(),
            prop=property_key,
            limit=limit,
        )

        if use_cache:
            cached_data = await self.cache.get_cached(cache_key)
            if cached_data is not None:
                return cached_data

        logger.info(
            "Fetching property breakdown",
            org_id=organization_id,
            prop=property_key,
            limit=limit,
            range=(start, end),
        )

        breakdown = await self.repo.get_breakdown(
            organization_id, start, end, property_key, limit
        )

        # Cache response for 5 minutes (300 seconds)
        await self.cache.set_cached(cache_key, breakdown, ttl=300)

        return breakdown
