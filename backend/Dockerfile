# ===================
# Builder Stage
# ===================
FROM python:3.12-slim AS builder

# [최적화] uv 설치 및 캐시 관련 환경변수 설정
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/uv.lock ./

# [최적화] --mount=type=cache를 사용하여 패키지 다운로드 속도 최적화
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ===================
# Base Runtime
# ===================
FROM python:3.12-slim AS base

WORKDIR /app

# [최적화] 실행 시에는 컴파일된 라이브러리(libpq5)만 있어도 충분하지만, 
# 기존 환경과의 정합성을 위해 libpq-dev 유지
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ===================
# Deployment Stage (Dev)
# ===================
FROM base AS dev

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY --from=builder /app/.venv /app/.venv
COPY backend/pyproject.toml backend/uv.lock ./

# [최적화] 개발 환경에서도 캐시 마운트 적용
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

CMD ["uvicorn", "catchup.server.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ===================
# Production Stage
# ===================
FROM base AS prod

# 빌드 단계에서 생성된 .venv 복사
COPY --from=builder /app/.venv /app/.venv

# 소스 코드 및 설정 복사
COPY backend/catchup ./catchup
COPY backend/pyproject.toml ./
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic

COPY backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]