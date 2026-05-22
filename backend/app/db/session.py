from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Verify database connection scheme is async-compatible (uses asyncpg driver)
if not settings.DATABASE_URL.startswith("postgresql+asyncpg://"):
    logger.critical(
        "Invalid database URL driver configuration. SQLAlchemy async requires the asyncpg driver.",
        database_url=settings.DATABASE_URL,
    )
    raise ValueError("Database URL must utilize the 'postgresql+asyncpg' scheme.")

# Create high-performance SQLAlchemy Async Database Engine
# Incorporates connection pool tuning and automatic pre-ping checks
logger.info(
    "Initializing SQLAlchemy async database engine",
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True for verbose raw SQL debugging in local dev
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,  # Automatically tests connection health before executing queries
    pool_recycle=1800,   # Recycles connections every 30 minutes to avoid stale sockets
)

# AsyncSessionmaker serves as a factory for thread-safe AsyncSession sessions
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevents SQLAlchemy from reloading objects after commit
    autocommit=False,
    autoflush=False,
)
