#!/bin/bash
# Start script for Railway single-service deployment
# Launches Celery worker in background + Uvicorn in foreground

echo "Starting Celery worker in background..."
celery -A celery_worker.celery_app worker --loglevel=info --pool=solo --concurrency=1 &

echo "Starting FastAPI server on port ${PORT:-8000}..."
python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
