#!/bin/sh
set -e

echo "Applying database migrations with Alembic..."
alembic upgrade head
echo "Database migrations applied successfully."

echo "Starting application server..."
exec "$@"
