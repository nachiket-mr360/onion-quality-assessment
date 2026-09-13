# ONIONVISION — existing FastAPI + YOLOv8 app (CPU).
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend:/app/cv \
    PIP_NO_CACHE_DIR=1 \
    MODEL_PATH=/app/runs/fresh_yolov8n_293_final/weights/best.pt \
    DATABASE_PATH=/app/data/onion_quality.db \
    REPORT_DIR=/app/captures/reports

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend
COPY cv /app/cv
COPY frontend /app/frontend
COPY runs/fresh_yolov8n_293_final/weights/best.pt \
     /app/runs/fresh_yolov8n_293_final/weights/best.pt

RUN mkdir -p /app/data /app/captures/reports

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=8)"

# Same app as local: backend.main, lifespan loads model + SQLite.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
