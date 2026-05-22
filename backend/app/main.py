from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import structlog

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import CorrelationIdMiddleware
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.test_auth import router as test_auth_router
from app.api.v1.invitation import router as invitation_router
from app.api.v1.api_key import router as api_key_router
from app.api.v1.data_source import router as data_source_router
from app.api.v1.ingest import router as ingest_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.ws import router as ws_router
from app.api.v1.alert import router as alert_router
from app.api.v1.report import router as report_router
from app.api.v1.sandbox import router as sandbox_router





# Configure structured logging at import time
configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and shutdown hook lifecycles.
    
    Ensures safe initialization and cleanup of connections.
    """
    logger.info(
        "Application bootstrapping initiated",
        environment=settings.ENVIRONMENT,
        project=settings.PROJECT_NAME,
        log_level=settings.LOG_LEVEL,
    )
    
    # Placeholders for connection pool checks (DB, Redis) to be filled in Steps 2 & 3
    
    yield
    
    logger.info("Application teardown completed safely")


# Instantiate the FastAPI Application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Production-grade SaaS Real-Time Analytics & Reporting Platform API.",
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# 1. Register Centralized HTTP Exception Handlers
register_exception_handlers(app)

# 2. Wire Cross-Origin Resource Sharing (CORS) Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Wire Request Trace / Correlation ID Middleware
app.add_middleware(CorrelationIdMiddleware)

# 4. Mount Application API Routers
app.include_router(health_router, prefix="/api/v1", tags=["Diagnostics"])
app.include_router(auth_router, prefix="/api/v1")
app.include_router(test_auth_router, prefix="/api/v1")
app.include_router(invitation_router, prefix="/api/v1")
app.include_router(api_key_router, prefix="/api/v1")
app.include_router(data_source_router, prefix="/api/v1")
app.include_router(ingest_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")
app.include_router(alert_router, prefix="/api/v1")
app.include_router(report_router, prefix="/api/v1")
app.include_router(sandbox_router, prefix="/api/v1")






@app.get("/", include_in_schema=False)
async def root_redirect() -> Any:
    """Redirects base path access to Swagger or returns a flat health check in production."""
    if settings.ENVIRONMENT != "production":
        return RedirectResponse(url="/docs")
    return {"status": "healthy", "service": settings.PROJECT_NAME}

