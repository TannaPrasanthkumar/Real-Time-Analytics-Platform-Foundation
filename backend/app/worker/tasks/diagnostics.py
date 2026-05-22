from typing import Dict, Any
import time
import structlog

from app.worker.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="app.worker.tasks.diagnostics.verify_worker_health")
def verify_worker_health() -> Dict[str, Any]:
    """Simple diagnostic task validating Celery worker availability and execution speed."""
    start_time = time.perf_counter()
    logger.info("Starting background worker diagnostics check")
    
    # Simulate processing delay
    time.sleep(0.05)
    
    latency = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info("Diagnostics check complete", latency_ms=latency)
    
    return {
        "status": "operational",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "latency_ms": latency,
        "worker_thread": "active"
    }


@celery_app.task(name="app.worker.tasks.diagnostics.periodic_heartbeat_check")
def periodic_heartbeat_check() -> None:
    """Periodic Celery Beat scheduled task executing every 60 seconds.
    
    Simulates background evaluation checks (like scanning metrics for active alerts).
    """
    logger.info(
        "Celery Beat scheduled heartbeat pulse executed",
        active_alert_rules=8,
        active_aggregations="healthy",
    )
