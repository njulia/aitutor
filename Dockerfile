FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV TOKENIZERS_PARALLELISM=false
ENV OMP_NUM_THREADS=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home --uid 10001 appuser

COPY --chown=appuser:appuser . .

RUN mkdir -p /app/uploads /app/data \
    && chown -R appuser:appuser /app/uploads /app/data

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent --show-error "http://127.0.0.1:${PORT}/api/health" || exit 1

CMD ["sh", "-c", "exec uvicorn web_app:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --workers ${WEB_CONCURRENCY:-1} --backlog 2048 --timeout-keep-alive 10 --timeout-graceful-shutdown 30"]
