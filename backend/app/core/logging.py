import logging
import sys
from typing import Any, Dict
import structlog
from structlog.types import EventDict, Processor

from app.core.config import settings

# Shared context variable mapping for thread/task-local storage
# This allows tracing correlation IDs dynamically across tasks and requests
import contextvars

correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def inject_correlation_id(
    logger: Any, method_name: str, event_dict: EventDict
) -> EventDict:
    """Injects the current context correlation_id into the log record."""
    cid = correlation_id_ctx.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def configure_logging() -> None:
    """Configures structured logging with structlog.
    
    Uses colorized console logs for development and JSON format for production.
    """
    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    
    log_level = log_level_map.get(settings.LOG_LEVEL.upper(), logging.INFO)

    # Core shared processors for structlog
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        inject_correlation_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.ENVIRONMENT == "production":
        # Production JSON-formatted logs
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Development human-readable, colorized logs
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging to redirect through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Suppress verbose standard logs from third party modules
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
