#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Run database migrations
echo "==> Running database migrations..."
poetry run alembic upgrade head

# Start Celery Worker in the background
echo "==> Starting Celery Worker..."
poetry run celery -A app.core.celery_app worker --loglevel=info &

# Start Celery Beat (Scheduler) in the background
echo "==> Starting Celery Scheduler (Beat)..."
poetry run celery -A app.core.celery_app beat --loglevel=info &

# Start FastAPI Web Gateway in the foreground
echo "==> Starting FastAPI Web Gateway..."
exec poetry run uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
