#!/bin/bash
set -e

# DB 서버 응답 대기
echo "Checking database connection (${DB_HOST}:${DB_PORT})..."
until python -c "import socket; s = socket.socket(); s.connect(('${DB_HOST}', ${DB_PORT}))" 2>/dev/null; do
  echo "Waiting for database..."
  sleep 1
done
echo "Database is up!"

echo "----------------------------------------"
echo "Migration Status Check"
# 현재 DB에 찍힌 리비전 확인
CURRENT_REV=$(alembic current 2>/dev/null | grep -oE '^[0-9a-f]+' || echo "")
echo "Current DB Revision: ${CURRENT_REV:-None}"
echo "----------------------------------------"

# 마이그레이션 실행
echo "Running migrations (alembic upgrade head)..."

if ! alembic upgrade head; then
    echo "Migration failed: check for conflicting revisions or existing tables."
    exit 1
fi

echo "----------------------------------------"
echo "Final Revision:"
alembic current
echo "----------------------------------------"

# 애플리케이션 실행
echo "Starting application with Uvicorn..."
exec uvicorn catchup.server.main:app --host 0.0.0.0 --port 8000