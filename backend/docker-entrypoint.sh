#!/bin/bash
set -e

echo "=== Voice Agent Backend Starting ==="

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

echo "Migrations complete!"

# Execute the main command
echo "Starting application server..."
exec "$@"
