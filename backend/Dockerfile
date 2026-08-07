FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Note: build context is the PROJECT ROOT (see docker-compose.yml), not this
# backend/ folder, so paths below are relative to the repo root. This lets
# us bake tests/ into the image too, so `pytest` works with no runtime
# volume mount - avoids Windows/Git-Bash path-translation issues entirely.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY tests/ /app/tests

ENV FLASK_APP=app.py
EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "app:app"]

