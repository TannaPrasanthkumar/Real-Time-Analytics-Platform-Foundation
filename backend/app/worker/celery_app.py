import celery
import structlog
from app.core.logging import correlation_id_ctx

logger = structlog.get_logger(__name__)


class TracePropagatingTask(celery.Task):
    """Custom Celery Task base class propagating tracing correlation IDs.
    
    Automatically extracts correlation headers from incoming Redis payloads, 
    binding them to the thread-local contextvars for structlog.
    """

    def __call__(self, *args, **kwargs):
        # 1. Resolve Correlation ID from task execution headers
        request_headers = self.request.headers or {}
        correlation_id = request_headers.get("correlation_id", "")

        # 2. Bind thread-safely in contextvars
        token = correlation_id_ctx.set(correlation_id)
        
        # Bind logger parameters
        structlog.contextvars.bind_contextvars(
            task_id=self.request.id,
            task_name=self.name,
            correlation_id=correlation_id,
        )

        logger.info("Celery Task execution initiated")
        
        try:
            # 3. Proceed with standard task execution
            return super().__call__(*args, **kwargs)
        except Exception as e:
            logger.exception("Celery Task execution crashed with unhandled exception", error=str(e))
            raise e
        finally:
            # Reset logger binding and context variables to prevent leaks
            structlog.contextvars.unbind_contextvars("task_id", "task_name", "correlation_id")
            correlation_id_ctx.reset(token)


# Instantiate the global Celery Application
celery_app = celery.Celery(
    "analytics_platform_worker",
    task_cls=TracePropagatingTask,  # Override standard Task class to use trace propagation
)

# Load fine-tuned Celery configuration modules
celery_app.config_from_object("app.core.celery_config")

# Automatically search and discover registered task modules inside app.worker.tasks
celery_app.autodiscover_tasks(["app.worker"])
