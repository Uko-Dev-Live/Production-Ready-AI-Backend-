# ─────────────────────────────────────────────────────────────
#  Stage 1 — Base image with Python dependencies
#  We use a slim Debian-based image to keep the final image small
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies needed for psycopg2 and other libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ─────────────────────────────────────────────────────────────
#  Stage 2 — Install Python packages
# ─────────────────────────────────────────────────────────────
FROM base AS dependencies

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────────────────────────
#  Stage 3 — Final application image
# ─────────────────────────────────────────────────────────────
FROM dependencies AS final

# Copy the full project into the container
COPY . .

# Create a non-root user for security best practices
RUN adduser --disabled-password --gecos "" appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose the port FastAPI listens on
EXPOSE 8000

# Default command: start the API server
# Override in docker-compose for Celery workers
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
