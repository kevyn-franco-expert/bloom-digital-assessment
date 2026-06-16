FROM python:3.11-slim

WORKDIR /app

# Install build dependencies for compiled packages (e.g. asyncpg, uvloop).
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata and source.
# README.md is required by pyproject.toml; source must exist for the editable install.
COPY pyproject.toml pytest.ini README.md ./
COPY app ./app
COPY tests ./tests
COPY docker ./docker

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[dev]"

RUN chmod +x ./docker/entrypoint.sh

# Run as a non-root user.
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["./docker/entrypoint.sh"]
