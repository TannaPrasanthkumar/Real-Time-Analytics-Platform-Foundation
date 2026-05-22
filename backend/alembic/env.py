import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 1. Import local settings configuration and model registry
from app.core.config import settings
from app.models.base import metadata

# this is the Alembic Config object, which provides access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 2. Dynamic Database URL Injection
# We dynamically inject the validated Pydantic settings database URL to avoid storing credentials in alembic.ini
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# 3. Target Metadata Registry Binding for Autogenerate
target_metadata = metadata


def do_run_migrations(connection) -> None:
    """Helper running migrations in a synchronous connection context."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # Enables batch migrations for safety across schema alterations
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Establish async connection engine and run online migrations."""
    # Build engine configuration from alembic properties
    configuration = config.get_section(config.config_ini_section, {})
    
    # Force use of asyncpg pooling options
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # Executes migrations inside a synchronous executor thread
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    
    This configures the context with just a URL and not a Connection,
    allowing query script generation (SQL dumps) without DB access.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.
    
    Determines execution loop state and dispatches either standard or async paths.
    """
    try:
        # Run migrations using the active running asyncio loop if applicable
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Create a new event loop if none is running
        loop = None

    if loop and loop.is_running():
        # Dispatch migration tasks to the running event loop
        loop.create_task(run_async_migrations())
    else:
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
