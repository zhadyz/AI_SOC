# Alert Triage Service - Dockerfile
# AI-Augmented SOC - Production Grade

FROM python:3.11-slim

# Metadata
LABEL maintainer="abdul.bari8019@coyote.csusb.edu"
LABEL version="1.0.0"
LABEL description="LLM-powered security alert triage service"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 triageuser && chown -R triageuser:triageuser /app
USER triageuser

# Expose FastAPI port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run FastAPI with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
