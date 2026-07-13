# Mnema MCP server — Python image.
#
# Installs from GitHub (Mnema is NOT on PyPI). Default: Chroma backend +
# local embeddings (offline). Override backend at runtime with
# MNEMA_BACKEND / MNEMA_BACKEND_PATH.

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install uv (fast installer) and clone Mnema from GitHub.
RUN pip install --no-cache-dir uv \
    && git clone --depth 1 https://github.com/mienetic/mnema /app/mnema

WORKDIR /app/mnema/packages/mnema-python

# Create a venv and install with the default extras.
# Override MNEMA_EXTRAS at build time to pick different backends:
#   docker build --build-arg MNEMA_EXTRAS=all -t mnema .
ARG MNEMA_EXTRAS=default
RUN uv venv --python 3.11 /app/.venv \
    && VIRTUAL_ENV=/app/.venv uv pip install -e ".[${MNEMA_EXTRAS}]"

# Default config — override at runtime.
ENV MNEMA_BACKEND=chroma \
    MNEMA_BACKEND_PATH=/data/mnema \
    MNEMA_DEFAULT_SCOPE=global \
    MNEMA_TRANSPORT=http \
    MNEMA_HTTP_HOST=0.0.0.0 \
    MNEMA_HTTP_PORT=8000 \
    PATH="/app/.venv/bin:$PATH"

VOLUME ["/data"]
EXPOSE 8000

# Streamable HTTP entrypoint.
CMD ["mnema", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
