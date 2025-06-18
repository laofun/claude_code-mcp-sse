#!/bin/bash
# Database migration script

set -e

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Default values
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-mcp_dev}
DB_USER=${DB_USER:-mcp_user}
DB_PASSWORD=${DB_PASSWORD:-mcp_password}

echo "Running database migrations..."

# Parse DATABASE_URL if provided
if [ ! -z "$DATABASE_URL" ]; then
    # Extract components from DATABASE_URL
    # Format: postgresql://user:password@host:port/database
    DB_USER=$(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    DB_PASSWORD=$(echo $DATABASE_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
fi

# Export for psql
export PGPASSWORD=$DB_PASSWORD

# Create database if it doesn't exist
echo "Ensuring database exists..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || \
    psql -h $DB_HOST -p $DB_PORT -U $DB_USER -c "CREATE DATABASE $DB_NAME"

# Run migrations
for migration in migrations/*.sql; do
    if [ -f "$migration" ]; then
        echo "Running migration: $migration"
        psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f "$migration"
    fi
done

echo "Migrations completed successfully!"

# Clean up
unset PGPASSWORD