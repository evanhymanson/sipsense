FROM python:3.11-slim

# System deps for PostgreSQL client, image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/sipsense/backend

# Install CPU-only PyTorch first (saves ~1.5GB vs CUDA version)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create uploads directory and non-root user
RUN useradd -m -u 1000 appuser \
    && mkdir -p uploads \
    && chown -R appuser:appuser /opt/sipsense/backend

USER appuser

EXPOSE 8000

# Override gunicorn bind to 0.0.0.0 so other containers can reach it
CMD ["gunicorn", "app.main:app", \
     "-c", "/opt/sipsense/deploy/gunicorn.conf.py", \
     "-b", "0.0.0.0:8000"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1
