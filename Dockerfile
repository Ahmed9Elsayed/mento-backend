# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS builder

# Install uv installer tool
COPY --from=astralsh/uv:latest /uv /uvx /bin/

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1 \
    UV_LINK_MODE=copy

WORKDIR /build

# Copy configuration files for uv package alignment
COPY pyproject.toml uv.lock ./

# Create virtual environment and install optimized CPU torch + your dynamically updated project dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv "$VIRTUAL_ENV" \
    && uv pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && uv pip install --extra-index-url https://download.pytorch.org/whl/cpu gunicorn \
    && uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1 \
    HF_HOME=/tmp/huggingface \
    XDG_CACHE_HOME=/tmp/.cache \
    USE_LOCAL_EMOTION_MODEL=false \
    FLASK_RUN_HOST=0.0.0.0 \
    FLASK_RUN_PORT=7860 \
    FLASK_DEBUG=false

WORKDIR /app

RUN addgroup --system mento \
    && adduser --system --ingroup mento --home /app mento \
    && chown -R mento:mento /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=mento:mento app.py components.py feedback_service.py mento_pipeline.py prompts.py rag_service.py settings.py ./
COPY --chown=mento:mento models/module1 ./models/module1

USER mento

EXPOSE 7860

CMD ["gunicorn", \
     "--bind", "0.0.0.0:7860", \
     "--workers", "1", \
     "--threads", "8", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]