FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install -r /app/backend/requirements.txt setuptools==80.3.1
COPY backend /app/backend
RUN python -m pip install --no-deps --no-build-isolation /app/backend \
    && useradd --create-home --uid 10001 visionguard
COPY workers /app/workers
COPY scripts /app/scripts
USER visionguard
EXPOSE 8000
CMD ["uvicorn", "visionguard.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
