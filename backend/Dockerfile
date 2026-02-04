# ===================
# Builder Stage
# ===================
FROM python:3.12-slim as builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

# ===================
# Base Runtime
# ===================
FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

    
# ===================
# Deployment Stage
# ===================
FROM base AS dev

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY --from=builder /app/.venv /app/.venv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project

CMD ["uvicorn", "catchup.server.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ===================
# Production Stage
# ===================
FROM base AS prod

COPY --from=builder /app/.venv /app/.venv

COPY catchup ./catchup
COPY README.md pyproject.toml ./

CMD ["uvicorn", "catchup.server.main:app", "--host", "0.0.0.0", "--port", "8000"]