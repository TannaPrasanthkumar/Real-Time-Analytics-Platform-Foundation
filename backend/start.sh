#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Activate virtual environment if it exists (Railway Railpack installs it here)
if [ -d "/app/.venv" ]; then
    echo "==> Activating virtual environment..."
    source /app/.venv/bin/activate
fi

# Run database migrations
echo "==> Running database migrations..."
alembic upgrade head

# Start Celery Worker in the background
echo "==> Starting Celery Worker..."
celery -A app.core.celery_app worker --loglevel=info &

# Start Celery Beat (Scheduler) in the background
echo "==> Starting Celery Scheduler (Beat)..."
celery -A app.core.celery_app beat --loglevel=info &

# Start FastAPI Web Gateway in the foreground
echo "==> Starting FastAPI Web Gateway..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
