import asyncio
import structlog
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from app.worker.celery_app import celery_app
from app.worker.tasks.ingestion import run_async_safely

logger = structlog.get_logger(__name__)


async def _execute_alerts_evaluation() -> Dict[str, Any]:
    """Coroutine to execute evaluations on all active alert rules."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import text
    from app.core.config import settings
    from app.repositories.alert import AlertRuleRepository
    from app.services.alert import AlertService

    # Create a dedicated local engine for the worker thread to prevent cross-loop conflicts
    local_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    local_session = async_sessionmaker(
        bind=local_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    evaluated_count = 0
    transitions_count = 0
    
    try:
        async with local_session() as session:
            rule_repo = AlertRuleRepository(session)
            alert_service = AlertService(session)
            
            # 1. Load all active alert rules
            rules = await rule_repo.get_all_enabled()
            logger.info("Retrieved active alert rules for evaluation", active_count=len(rules))
            
            for rule in rules:
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(minutes=rule.time_window_minutes)
                
                # 2. Query metric aggregate based on configured type
                current_value = 0.0
                
                if rule.metric_type == "page_views":
                    q = text("""
                        SELECT COUNT(*) 
                        FROM events 
                        WHERE organization_id = :org_id 
                          AND event_name IN ('page_view', 'page.view') 
                          AND timestamp >= :start AND timestamp <= :end
                    """)
                    res = await session.execute(q, {"org_id": rule.organization_id, "start": start_time, "end": end_time})
                    current_value = float(res.scalar() or 0)
                    
                elif rule.metric_type == "error_count":
                    q = text("""
                        SELECT COUNT(*) 
                        FROM events 
                        WHERE organization_id = :org_id 
                          AND event_name = 'error' 
                          AND timestamp >= :start AND timestamp <= :end
                    """)
                    res = await session.execute(q, {"org_id": rule.organization_id, "start": start_time, "end": end_time})
                    current_value = float(res.scalar() or 0)
                    
                elif rule.metric_type == "error_rate":
                    q = text("""
                        SELECT 
                            COALESCE(
                                COUNT(*) FILTER (WHERE event_name = 'error') * 100.0 / NULLIF(COUNT(*), 0), 
                                0.0
                            )
                        FROM events 
                        WHERE organization_id = :org_id 
                          AND timestamp >= :start AND timestamp <= :end
                    """)
                    res = await session.execute(q, {"org_id": rule.organization_id, "start": start_time, "end": end_time})
                    current_value = float(res.scalar() or 0.0)
                    
                elif rule.metric_type == "unique_visitors":
                    q = text("""
                        SELECT COUNT(DISTINCT COALESCE(payload ->> 'user_id', payload ->> 'visitor_id', payload ->> 'anonymous_id')) 
                        FROM events 
                        WHERE organization_id = :org_id 
                          AND timestamp >= :start AND timestamp <= :end
                    """)
                    res = await session.execute(q, {"org_id": rule.organization_id, "start": start_time, "end": end_time})
                    current_value = float(res.scalar() or 0)
                    
                elif rule.metric_type == "bounce_rate":
                    q = text("""
                        WITH stats AS (
                            SELECT 
                                payload ->> 'session_id' AS session_id,
                                COUNT(*) AS count
                            FROM events 
                            WHERE organization_id = :org_id 
                              AND timestamp >= :start AND timestamp <= :end
                              AND payload ->> 'session_id' IS NOT NULL
                            GROUP BY payload ->> 'session_id'
                        )
                        SELECT 
                            COALESCE(
                                (COUNT(*) FILTER (WHERE count = 1) * 100.0) / NULLIF(COUNT(*), 0),
                                0.0
                            )
                        FROM stats
                    """)
                    res = await session.execute(q, {"org_id": rule.organization_id, "start": start_time, "end": end_time})
                    current_value = float(res.scalar() or 0.0)
                    
                elif rule.metric_type == "avg_session_duration":
                    q = text("""
                        WITH stats AS (
                            SELECT 
                                payload ->> 'session_id' AS session_id,
                                EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) AS duration
                            FROM events 
                            WHERE organization_id = :org_id 
                              AND timestamp >= :start AND timestamp <= :end
                              AND payload ->> 'session_id' IS NOT NULL
                            GROUP BY payload ->> 'session_id'
                        )
                        SELECT COALESCE(AVG(duration), 0.0) FROM stats
                    """)
                    res = await session.execute(q, {"org_id": rule.organization_id, "start": start_time, "end": end_time})
                    current_value = float(res.scalar() or 0.0)
                
                # 3. Evaluate Rule Transitions using AlertService
                new_history = await alert_service.evaluate_rule(rule, current_value)
                evaluated_count += 1
                if new_history:
                    transitions_count += 1
                    logger.info(
                        "Alert state transition triggered",
                        rule_name=rule.name,
                        new_state=rule.current_state,
                        value=current_value
                    )
                    
        return {
            "success": True,
            "evaluated": evaluated_count,
            "transitions": transitions_count
        }
    finally:
        await local_engine.dispose()


@celery_app.task(
    name="app.worker.tasks.alert.evaluate_alerts_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def evaluate_alerts_task(self) -> Dict[str, Any]:
    """Celery Beat periodic task scanning and evaluating metric thresholds for all active alert rules."""
    logger.info("Scheduled alerts evaluation scanner sweep started")
    try:
        result = run_async_safely(_execute_alerts_evaluation())
        logger.info(
            "Scheduled alerts evaluation scanner sweep completed successfully",
            evaluated_count=result["evaluated"],
            transitions_count=result["transitions"]
        )
        return result
    except Exception as exc:
        logger.error("Error occurred during scheduled alerts evaluation", error=str(exc))
        raise self.retry(exc=exc, countdown=60)
