FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TOKENIZERS_PARALLELISM=false \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1

# System deps for building wheels (torch/transformers) and curl for HF healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first to leverage Docker layer caching
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt \
    && pip install gunicorn

# Copy application source
COPY . /app

# Hugging Face Spaces expects the app to listen on 0.0.0.0:7860
ENV FLASK_RUN_HOST=0.0.0.0 \
    FLASK_RUN_PORT=7860 \
    FLASK_DEBUG=false

EXPOSE 7860

# Disable local emotion model in the Space by default; it's heavy and not always needed.
# Set USE_LOCAL_EMOTION_MODEL=true as a Space secret to opt in.
ENV USE_LOCAL_EMOTION_MODEL=false

# Use gunicorn with a single worker but multiple threads (matches threaded=True in app.py).
# SSE streaming benefits from threads, not multiple workers (sticky sessions needed otherwise).
CMD ["gunicorn", \
     "--bind", "0.0.0.0:7860", \
     "--workers", "1", \
     "--threads", "8", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
