# Log Summarization Service - Dockerfile
# AI-Augmented SOC - Production Grade

FROM python:3.11-slim

# Metadata
LABEL maintainer="abdul.bari8019@coyote.csusb.edu"
LABEL version="1.0.0"
LABEL description="LLM-powered log summarization service"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 summarizer && chown -R summarizer:summarizer /app
USER summarizer

# Expose FastAPI port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Run FastAPI with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "2"]
