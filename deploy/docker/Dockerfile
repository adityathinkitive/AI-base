# Build from repo root:  docker build -f deploy/docker/Dockerfile --build-arg SERVICE=rag -t rag .
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
# Add `--extra presidio --extra faster-whisper` etc. for the adapters this service selects.
ARG EXTRAS=""
RUN uv sync --frozen --no-dev --no-install-project ${EXTRAS}

FROM python:3.12-slim
ARG SERVICE
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY libs ./libs
COPY services/${SERVICE}/src ./services/${SERVICE}/src
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/libs:/app/services/${SERVICE}/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SERVICE_MODULE=${SERVICE}_service.main:create_service_app
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"
CMD ["sh", "-c", "exec uvicorn $SERVICE_MODULE --factory --host 0.0.0.0 --port 8000 --no-server-header"]
