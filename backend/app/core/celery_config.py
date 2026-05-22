from app.core.config import settings

# Active Celery Configuration settings
# Reference: https://docs.celeryq.dev/en/stable/userguide/configuration.html

broker_url = settings.CELERY_BROKER_URL
result_backend = settings.CELERY_RESULT_BACKEND

# Serialization settings (strictly use JSON for cross-environment safety)
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]

# Timezone alignment
timezone = "UTC"
enable_utc = True

# Task result management
# Ignore results by default to save Redis memory space, opting-in only where strictly required
task_ignore_result = True
result_expires = 3600  # Expire cached task results after 1 hour

# Concurrency & Ingestion tuning
# Standard prefetch limit = 1 ensures workers don't lock massive chunks of events exclusively,
# facilitating balanced task load sharing across horizontal container instances.
worker_prefetch_multiplier = 1

# Broker resilience settings
# Graceful connection retries on container startup to tolerate slow broker boots
broker_connection_retry_on_startup = True
broker_connection_max_retries = 10

# Task routing definition
# Segregate short, high-throughput tasks (e.g. event ingestion) from CPU-heavy operations
task_routes = {
    "app.worker.tasks.ingestion.*": {"queue": "ingestion"},
    "app.worker.tasks.diagnostics.*": {"queue": "default"},
    "app.worker.tasks.alerts.*": {"queue": "default"},
    "app.worker.tasks.report.*": {"queue": "default"},
    "app.worker.tasks.db_maintenance.*": {"queue": "default"},
}

# ==============================================================================
# Celery Beat Periodic Scheduled Tasks Registry
# ==============================================================================
beat_schedule = {
    "diagnostics-heartbeat-every-minute": {
        "task": "app.worker.tasks.diagnostics.periodic_heartbeat_check",
        "schedule": 60.0,  # Execute every 60 seconds
    },
    "db-partition-maintenance-daily": {
        "task": "app.worker.tasks.db_maintenance.preprovision_partitions",
        "schedule": 86400.0,  # Execute once every 24 hours
    },
    "evaluate-alerts-every-minute": {
        "task": "app.worker.tasks.alert.evaluate_alerts_task",
        "schedule": 60.0,  # Execute every 60 seconds
    },
    "evaluate-scheduled-reports-every-minute": {
        "task": "app.worker.tasks.report.evaluate_scheduled_reports_task",
        "schedule": 60.0,  # Execute every 60 seconds
    }
}


