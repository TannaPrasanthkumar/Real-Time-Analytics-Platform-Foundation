import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from app.core.logging import correlation_id_ctx

logger = structlog.get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware for injecting, tracking, and propagating request correlation IDs.
    
    Acts as the entry boundary for request tracing across synchronous APIs, 
    asynchronous workers, databases, and client interactions.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        # 1. Resolve Correlation ID from headers or generate a new one
        header_cid = request.headers.get("x-correlation-id")
        correlation_id = header_cid if header_cid else str(uuid.uuid4())

        # 2. Bind the ID thread-safely in contextvars for structlog to consume
        token = correlation_id_ctx.set(correlation_id)
        
        # 3. Store the correlation ID in the request state for exception handlers
        request.state.correlation_id = correlation_id

        # Log request entrance
        logger.info(
            "HTTP Request Received",
            method=request.method,
            path=request.url.path,
            client_host=request.client.host if request.client else "unknown",
            correlation_id=correlation_id,
        )

        try:
            # 4. Proceed with request downstream execution
            response: Response = await call_next(request)
        except Exception as e:
            # ContextVar is still bound during exception processing
            duration = time.perf_counter() - start_time
            logger.error(
                "HTTP Request Pipeline Exception",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration * 1000, 2),
                correlation_id=correlation_id,
                error=str(e),
            )
            raise e
        finally:
            # Reset ContextVar to prevent memory leaks across async tasks
            correlation_id_ctx.reset(token)

        # 5. Attach Correlation ID to outbound headers for client traceability
        response.headers["x-correlation-id"] = correlation_id
        
        # Log request exit
        duration = time.perf_counter() - start_time
        logger.info(
            "HTTP Request Completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
            correlation_id=correlation_id,
        )

        return response
