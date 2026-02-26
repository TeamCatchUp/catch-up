#!/bin/bash
set -e  # 에러 발생 시 스크립트 중단

echo "Waiting 5s for database..."
sleep 5

echo "Revision version (before migrations)"
alembic current

echo "Running migrations..."
alembic upgrade head

echo "Revision version (after migrations)"
alembic current

echo "Starting application..."
exec uvicorn catchup.server.main:app --host 0.0.0.0 --port 8000