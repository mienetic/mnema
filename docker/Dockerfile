# Mnema MCP server — Python image.
#
# Default: Chroma backend + local embeddings (offline). Override backend at
# runtime with MNEMA_BACKEND / MNEMA_BACKEND_PATH.

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install the package with the default extras.
# For other backends, build a derived image or override these extras.
RUN pip install --no-cache-dir 'mnema-mcp[default]'

# Default config — override at runtime.
ENV MNEMA_BACKEND=chroma \
    MNEMA_BACKEND_PATH=/data/mnema \
    MNEMA_DEFAULT_SCOPE=global \
    MNEMA_TRANSPORT=http \
    MNEMA_HTTP_HOST=0.0.0.0 \
    MNEMA_HTTP_PORT=8000

VOLUME ["/data"]
EXPOSE 8000

# Streamable HTTP entrypoint.
CMD ["mnema", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
