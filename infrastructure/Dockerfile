FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /bin/uv

# git is needed to read the version from the tag
RUN apt-get update -y && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_LINK_MODE=copy

# Install dependencies first so this layer is cached
COPY pyproject.toml uv.lock README.md /app/
RUN uv sync --locked --no-dev --no-install-project

# Install the app
COPY pv_site_api /app/pv_site_api/
COPY .git /app/.git
RUN uv sync --locked --no-dev --no-editable

ENV PATH="/app/.venv/bin:$PATH"
