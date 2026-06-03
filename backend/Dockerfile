FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Install dependencies (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Install project
COPY app/ ./app/
RUN uv sync --frozen --no-dev

# Raw-SQL migrations applied at startup (resolved relative to app/, i.e. /app/migrations)
COPY migrations/ ./migrations/

EXPOSE 8000

# Apply pending migrations, then start the server. Migrations run once before
# the uvicorn workers fork; yoyo takes its own lock so multiple replicas stay safe.
CMD ["sh", "-c", "uv run --no-dev --no-sync app migrate apply && exec uv run --no-dev --no-sync uvicorn app.server:deploy_factory --factory --host 0.0.0.0 --port 8000 --workers 2"]
