import asyncio
import structlog
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from app.worker.celery_app import celery_app
from app.worker.tasks.ingestion import run_async_safely

logger = structlog.get_logger(__name__)


async def _execute_partition_provisioning() -> Dict[str, Any]:
    """Execute raw DDL dynamically to pre-provision monthly partition buckets ahead of time."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from app.core.config import settings

    # Create a dedicated local engine for raw DDL execution to avoid event loop conflicts
    local_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
    )
    
    provisioned_partitions = []
    
    try:
        # Determine current date
        now = datetime.now(timezone.utc)
        
        # Pre-provision for the current month and the next 3 months to prevent ingestion gaps
        months_to_provision = []
        for i in range(4):
            # Calculate target year and month correctly handling rollover
            y = now.year
            m = now.month + i
            while m > 12:
                m -= 12
                y += 1
            
            # Start of this month
            start_year = y
            start_month = m
            
            # Start of next month
            end_year = y
            end_month = m + 1
            if end_month > 12:
                end_month = 1
                end_year += 1
                
            months_to_provision.append((start_year, start_month, end_year, end_month))

        async with local_engine.begin() as conn:
            for start_y, start_m, end_y, end_m in months_to_provision:
                partition_name = f"events_y{start_y}m{start_m:02d}"
                start_val = f"{start_y}-{start_m:02d}-01 00:00:00+00"
                end_val = f"{end_y}-{end_m:02d}-01 00:00:00+00"
                
                query = text(
                    f"CREATE TABLE IF NOT EXISTS {partition_name} "
                    f"PARTITION OF events FOR VALUES FROM ('{start_val}') TO ('{end_val}');"
                )
                
                logger.info(
                    "Ensuring event partition bucket exists",
                    partition=partition_name,
                    range_from=start_val,
                    range_to=end_val
                )
                await conn.execute(query)
                provisioned_partitions.append(partition_name)
                
        return {
            "success": True,
            "provisioned": provisioned_partitions,
        }
    finally:
        await local_engine.dispose()


@celery_app.task(
    name="app.worker.tasks.db_maintenance.preprovision_partitions",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def preprovision_partitions(self) -> Dict[str, Any]:
    """Periodic daemon task checking and auto-creating time-series partition tables."""
    logger.info("Database partition maintenance daemon execution started")
    try:
        result = run_async_safely(_execute_partition_provisioning())
        logger.info(
            "Database partition maintenance completed successfully",
            provisioned_count=len(result["provisioned"]),
            partitions=result["provisioned"]
        )
        return result
    except Exception as exc:
        logger.error("Failed to preprovision database range partitions", error=str(exc))
        raise self.retry(exc=exc, countdown=60)
