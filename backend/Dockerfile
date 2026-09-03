# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLCONFIGDIR=/tmp/matplotlib

# libgl/libglib: OpenCV runtime; ffmpeg: video and compressed-audio decoding.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-ml.txt ./
# Install the CPU torch build: the GPU wheels are ~2 GB and pointless without
# a GPU. Override with a CUDA base image when deploying to a GPU instance.
RUN pip install --index-url https://download.pytorch.org/whl/cpu \
        torch==2.4.1 torchvision==0.19.1 \
    && pip install -r requirements-ml.txt

COPY . .

# Run as a non-root user: this service accepts arbitrary uploads from the
# internet, so the process should not own the filesystem it writes to.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/storage /app/checkpoints \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
