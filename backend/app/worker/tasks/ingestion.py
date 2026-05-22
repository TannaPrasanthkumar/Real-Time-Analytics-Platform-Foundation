import asyncio
from typing import List, Dict, Any
import time
import random
import uuid
import threading
from datetime import datetime, timezone
import structlog
from app.worker.celery_app import celery_app
from app.db.session import async_session
from app.repositories.event import EventRepository

logger = structlog.get_logger(__name__)


async def _execute_bulk_insert(events_to_insert: List[Dict[str, Any]]) -> None:
    """Coroutine to execute the bulk insertion using a dedicated local engine."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.core.config import settings
    
    # Create a dedicated local engine for this worker task thread to avoid cross-loop pollution
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
            repo = EventRepository(session)
            await repo.bulk_insert_events(events_to_insert)
    finally:
        await local_engine.dispose()


def run_async_safely(coro) -> Any:
    """Run an async coroutine safely, whether inside a running event loop or a bare thread."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        # Running inside an active loop (e.g. synchronous apply() inside an async test).
        # Spin up a new thread to run standard asyncio.run to avoid event loop conflicts.
        res_list = []
        err_list = []
        
        def target():
            try:
                res_list.append(asyncio.run(coro))
            except Exception as e:
                err_list.append(e)

        thread = threading.Thread(target=target)
        thread.start()
        thread.join()

        if err_list:
            raise err_list[0]
        return res_list[0] if res_list else None
    else:
        # Standard bare thread (e.g. Celery worker prefork execution)
        return asyncio.run(coro)


@celery_app.task(
    name="app.worker.tasks.ingestion.ingest_event_batch",
    bind=True,
    max_retries=5,
    default_retry_delay=5,
)
def ingest_event_batch(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Asynchronous analytical event ingestion processor.
    
    Processes event schemas, executes normalizations, and executes bulk database 
    insertions inside transaction scopes. Implements exponential backoff retries.
    """
    logger.info("Asynchronous ingestion batch processing started", batch_size=len(events))
    
    try:
        start_time = time.perf_counter()
        
        # Parse fields (UUIDs and timestamps) back from JSON-serialized formats
        events_to_insert = []
        for ev in events:
            # Parse timestamp
            ts_val = ev.get("timestamp")
            if isinstance(ts_val, str):
                # Replace 'Z' suffix with standard '+00:00' to ensure ISO 8601 parsing success
                timestamp = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
            elif isinstance(ts_val, datetime):
                timestamp = ts_val
            else:
                timestamp = datetime.now(timezone.utc)

            # Parse UUID fields
            org_id = ev.get("organization_id")
            if isinstance(org_id, str):
                org_uuid = uuid.UUID(org_id)
            else:
                org_uuid = org_id

            ds_id = ev.get("data_source_id")
            if isinstance(ds_id, str):
                ds_uuid = uuid.UUID(ds_id)
            else:
                ds_uuid = ds_id

            ev_id = ev.get("id")
            if isinstance(ev_id, str):
                event_uuid = uuid.UUID(ev_id)
            elif isinstance(ev_id, uuid.UUID):
                event_uuid = ev_id
            else:
                event_uuid = uuid.uuid4()

            events_to_insert.append({
                "id": event_uuid,
                "organization_id": org_uuid,
                "data_source_id": ds_uuid,
                "event_name": ev.get("event_name"),
                "timestamp": timestamp,
                "payload": ev.get("payload") or {},
            })

        # Run async bulk insert safely
        run_async_safely(_execute_bulk_insert(events_to_insert))
        
        duration = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info("Ingestion batch writing completed successfully", batch_size=len(events), duration_ms=duration)
        
        return {
            "success": True,
            "processed_records": len(events),
            "duration_ms": duration,
        }
        
    except Exception as exc:
        # Determine retry backoff with exponential backoff & jitter
        # Formula: BaseDelay * 2^Attempt + Jitter
        attempt = self.request.retries
        backoff_delay = int((2 ** attempt) * 5 + random.uniform(0, 3))
        
        logger.warning(
            "Ingestion batch processing encountered error. Triggering retry task.",
            attempt=attempt,
            next_retry_seconds=backoff_delay,
            error=str(exc),
        )
        
        # Re-queue task into Celery with backoff delay
        raise self.retry(exc=exc, countdown=backoff_delay)

