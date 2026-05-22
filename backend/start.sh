#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Activate virtual environment if it exists (for compatibility)
if [ -d "/app/.venv" ]; then
    echo "==> Activating virtual environment..."
    source /app/.venv/bin/activate
fi

# Run database migrations
echo "==> Running database migrations..."
alembic upgrade head

# Start Celery Worker in the background (correct module path: app.worker.celery_app)
echo "==> Starting Celery Worker..."
celery -A app.worker.celery_app worker --loglevel=info &

# Start Celery Beat (Scheduler) in the background (correct module path: app.worker.celery_app)
echo "==> Starting Celery Scheduler (Beat)..."
celery -A app.worker.celery_app beat --loglevel=info &

# Start FastAPI Web Gateway in the foreground
echo "==> Starting FastAPI Web Gateway..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
