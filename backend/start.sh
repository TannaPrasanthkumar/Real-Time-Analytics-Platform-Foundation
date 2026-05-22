#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "=========================================="
echo "==> RUNTIME DIAGNOSTIC MODE <=="
echo "=========================================="
echo "Current User: $(whoami)"
echo "Current Directory: $(pwd)"
echo "PATH: $PATH"
echo "Listing current directory files:"
ls -la || true
echo "Listing /app directory files:"
ls -la /app || true
echo "Searching for alembic executable..."
find / -name "alembic" -type f 2>/dev/null || true
echo "Searching for .venv directory..."
find / -name ".venv" -type d 2>/dev/null || true
echo "=========================================="

# Activate virtual environment if it exists
if [ -d "/app/.venv" ]; then
    echo "==> Activating virtual environment at /app/.venv..."
    source /app/.venv/bin/activate
elif [ -d "/app/backend/.venv" ]; then
    echo "==> Activating virtual environment at /app/backend/.venv..."
    source /app/backend/.venv/bin/activate
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
