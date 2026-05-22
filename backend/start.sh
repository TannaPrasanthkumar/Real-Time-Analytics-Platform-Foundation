#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Force Celery to allow running as root (required in Docker containers)
export C_FORCE_ROOT="true"

# Activate virtual environment if it exists (for compatibility)
if [ -d "/app/.venv" ]; then
    echo "==> Activating virtual environment..."
    source /app/.venv/bin/activate
fi

# Run database migrations
echo "==> Running database migrations..."
alembic upgrade head

# Start Celery Worker in the background as unprivileged user 'nobody'
echo "==> Starting Celery Worker..."
celery -A app.worker.celery_app worker --loglevel=info --uid=nobody --pidfile=/tmp/celery_worker.pid &

# Start Celery Beat (Scheduler) in the background as unprivileged user 'nobody'
# Note: We specify writable /tmp paths for the database schedule and pidfile
echo "==> Starting Celery Scheduler (Beat)..."
celery -A app.worker.celery_app beat --loglevel=info --uid=nobody --schedule=/tmp/celerybeat-schedule --pidfile=/tmp/celerybeat.pid &

# Start FastAPI Web Gateway in the foreground
echo "==> Starting FastAPI Web Gateway..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
