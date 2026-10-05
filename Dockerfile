# ==============================================================================
# CareerLens — Production Dockerfile
# ==============================================================================

FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5001 \
    DATABASE_PATH=/app/data/careerlens.db

WORKDIR /app

# Install system dependencies (curl for container healthcheck)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for optimal Docker layer caching
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . /app/

# Create persistent storage directories for SQLite database and uploaded files
RUN mkdir -p /app/data /app/uploads && \
    useradd -u 1000 -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user for security best practice
USER appuser

# Expose service port
EXPOSE 5001

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5001/ || exit 1

# Start production WSGI server with multi-threaded workers
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--threads", "4", "--timeout", "120", "app:app"]
