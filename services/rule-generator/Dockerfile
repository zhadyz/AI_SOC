# Build with the repository root as context.
FROM python:3.11-slim
ARG SERVICE=rule-generator
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-runtime.txt ./
COPY ml_training/requirements-inference.txt ./ml_training/requirements-inference.txt
COPY dashboard/requirements.txt ./dashboard/requirements.txt
COPY services/alert-triage/requirements.txt ./services/alert-triage/requirements.txt
COPY services/correlation-engine/requirements.txt ./services/correlation-engine/requirements.txt
COPY services/feedback-service/requirements.txt ./services/feedback-service/requirements.txt
COPY services/rag-service/requirements.txt ./services/rag-service/requirements.txt
COPY services/response-orchestrator/requirements.txt ./services/response-orchestrator/requirements.txt
COPY services/retraining/requirements.txt ./services/retraining/requirements.txt
COPY services/rule-generator/requirements.txt ./services/rule-generator/requirements.txt
COPY services/wazuh-integration/requirements.txt ./services/wazuh-integration/requirements.txt
RUN if [ "$SERVICE" = "ml-inference" ]; then \
      pip install --no-cache-dir -r ml_training/requirements-inference.txt; \
    elif [ "$SERVICE" = "dashboard" ]; then \
      pip install --no-cache-dir -r dashboard/requirements.txt; \
    else \
      pip install --no-cache-dir -r "services/$SERVICE/requirements.txt"; \
    fi
COPY services/ ./services/
COPY ml_training/ ./ml_training/
COPY dashboard/ ./dashboard/
COPY config/ ./config/
RUN useradd --create-home --uid 1000 soc && mkdir -p /app/data && chown -R soc:soc /app
USER soc
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "services.rule_generator.main:app", "--host", "0.0.0.0", "--port", "8000"]
