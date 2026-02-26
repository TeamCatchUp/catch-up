#!/bin/bash
set -e

# DB 서버가 응답할 때까지 대기
echo "Checking database connection..."
for i in {1..30}; do
  if python -c "import socket; s = socket.socket(); s.connect(('${DB_HOST}', ${DB_PORT}))" 2>/dev/null; then
    echo "Database is up!"
    break
  fi
  echo "Waiting for database... ($i/30)"
  sleep 1
done

echo "----------------------------------------"
echo "Current Revision:"
alembic current || echo "No migrations found yet."
echo "----------------------------------------"

echo "Running migrations (alembic upgrade head)..."
alembic upgrade head

echo "----------------------------------------"
echo "Updated Revision:"
alembic current
echo "----------------------------------------"

echo "Starting application with Uvicorn..."
# exec를 사용해야 컨테이너의 PID 1을 uvicorn이 가져가서 종료 신호(SIGTERM)를 잘 받습니다.
exec uvicorn catchup.server.main:app --host 0.0.0.0 --port 8000