import asyncio
import structlog
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from app.worker.celery_app import celery_app
from app.worker.tasks.ingestion import run_async_safely

logger = structlog.get_logger(__name__)


async def _execute_scheduled_reports_evaluation() -> Dict[str, Any]:
    """Coroutine to scan all active report schedules and trigger due tasks."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select
    from app.core.config import settings
    from app.repositories.report import ReportScheduleRepository, ReportHistoryRepository
    from app.models.report import ReportHistory

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

    triggered_count = 0
    active_schedules_count = 0

    try:
        async with local_session() as session:
            schedule_repo = ReportScheduleRepository(session)
            # Fetch all active, non-deleted schedules
            schedules = await schedule_repo.get_all_active()
            active_schedules_count = len(schedules)
            
            logger.info("Scanning active report schedules for evaluation", active_count=active_schedules_count)

            for schedule in schedules:
                # Determine standard threshold for when a new report is due
                freq = schedule.frequency.lower()
                if freq == "daily":
                    due_delta = timedelta(hours=23)
                elif freq == "weekly":
                    due_delta = timedelta(days=6)
                elif freq == "monthly":
                    due_delta = timedelta(days=28)
                else:
                    due_delta = timedelta(hours=23) # fallback to daily

                # Query the latest success report in the history
                stmt = select(ReportHistory).where(
                    ReportHistory.report_schedule_id == schedule.id,
                    ReportHistory.status == "success",
                    ReportHistory.is_deleted == False
                ).order_by(ReportHistory.triggered_at.desc()).limit(1)

                res = await session.execute(stmt)
                last_history = res.scalar_one_or_none()

                is_due = False
                now_utc = datetime.now(timezone.utc)
                if not last_history:
                    # Never run before, trigger immediately
                    is_due = True
                else:
                    # Convert to timezone aware or timezone naive as needed
                    last_triggered = last_history.triggered_at
                    if last_triggered.tzinfo is None:
                        last_triggered = last_triggered.replace(tzinfo=timezone.utc)
                    if now_utc - last_triggered >= due_delta:
                        is_due = True

                if is_due:
                    logger.info("Report schedule is due, triggering async worker generator task", schedule_id=schedule.id, name=schedule.name)
                    generate_report_task.delay(str(schedule.id))
                    triggered_count += 1

        return {
            "success": True,
            "active_schedules": active_schedules_count,
            "triggered_reports": triggered_count
        }
    finally:
        await local_engine.dispose()


async def _execute_single_report_generation(schedule_uuid: uuid.UUID) -> Dict[str, Any]:
    """Coroutine to execute snapshot compilation and dispatching for a single schedule."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.core.config import settings
    from app.services.report import ReportService

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

    try:
        async with local_session() as session:
            report_service = ReportService(session)
            history_entry = await report_service.generate_dashboard_report(schedule_uuid)
            return {
                "success": True,
                "history_id": str(history_entry.id),
                "status": history_entry.status,
                "file_path": history_entry.file_path
            }
    finally:
        await local_engine.dispose()


@celery_app.task(
    name="app.worker.tasks.report.evaluate_scheduled_reports_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def evaluate_scheduled_reports_task(self) -> Dict[str, Any]:
    """Celery Beat periodic task scanning all active schedules and queuing execution tasks."""
    logger.info("Scheduled reports scanner sweep started")
    try:
        result = run_async_safely(_execute_scheduled_reports_evaluation())
        logger.info(
            "Scheduled reports scanner sweep completed successfully",
            active_count=result["active_schedules"],
            triggered_count=result["triggered_reports"]
        )
        return result
    except Exception as exc:
        logger.error("Error occurred during scheduled reports scan sweep", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(
    name="app.worker.tasks.report.generate_report_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def generate_report_task(self, schedule_id: str) -> Dict[str, Any]:
    """Worker task executing snapshot query compilation and archiving for a single schedule."""
    logger.info("Asynchronous report snapshot generation task started", schedule_id=schedule_id)
    try:
        schedule_uuid = uuid.UUID(schedule_id)
        result = run_async_safely(_execute_single_report_generation(schedule_uuid))
        logger.info("Asynchronous report snapshot generation completed successfully", schedule_id=schedule_id, status=result["status"])
        return result
    except Exception as exc:
        logger.error("Error occurred during asynchronous report snapshot generation", schedule_id=schedule_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)
