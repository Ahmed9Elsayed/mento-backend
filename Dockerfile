# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS builder

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TOKENIZERS_PARALLELISM=false \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1

WORKDIR /build

COPY requirements.txt ./
RUN python -m venv "$VIRTUAL_ENV"
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r requirements.txt gunicorn

FROM python:3.12-slim AS runtime

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
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
