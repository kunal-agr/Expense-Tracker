#!/bin/sh
set -e

echo "Applying database migrations..."
alembic upgrade head

PORT="${PORT:-8000}"
echo "Starting application server on port $PORT..."
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
