FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libvips42 \
    libglib2.0-0 \
    libgl1 \
    libglib2.0-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Install dependencies first (without project package) for better layer caching
RUN poetry config virtualenvs.create false \
    && poetry lock --no-update \
    && poetry install --no-interaction --no-ansi --extras selfhost --without dev --no-root

# Copy application source
COPY README.md ./
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

# Install the root project package without altering dependency selections
RUN pip install --no-cache-dir --no-deps -e .

EXPOSE 8000

# Run migrations then start the server
CMD ["sh", "-c", "alembic upgrade head && uvicorn photocurate.main:app --host 0.0.0.0 --port 8000"]
