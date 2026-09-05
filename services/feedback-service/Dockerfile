# Compatibility build: run docker build from the repository root with -f services/feedback-service/Dockerfile
FROM python:3.11-slim
ARG SERVICE=feedback-service
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-runtime.txt ./
COPY services/ ./services/
COPY ml_training/ ./ml_training/
COPY dashboard/ ./dashboard/
COPY config/ ./config/
RUN if [ "$SERVICE" = "ml-inference" ]; then \
      pip install --no-cache-dir -r ml_training/requirements-inference.txt; \
    elif [ "$SERVICE" = "dashboard" ]; then \
      pip install --no-cache-dir -r dashboard/requirements.txt; \
    else \
      pip install --no-cache-dir -r "services/$SERVICE/requirements.txt"; \
    fi
RUN useradd --create-home --uid 1000 soc && mkdir -p /app/data && chown -R soc:soc /app
USER soc
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "services.feedback_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
