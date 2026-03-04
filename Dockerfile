FROM python:3.11-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements-nba.txt .
RUN pip install --no-cache-dir -r requirements-nba.txt

COPY src/ src/
COPY sql/ sql/

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Default: run the API
CMD ["uvicorn", "nba_props.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
