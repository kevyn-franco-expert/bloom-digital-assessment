#!/usr/bin/env bash
set -euo pipefail

# Default command: run the FastAPI app.
if [ "$#" -eq 0 ]; then
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level info
fi

exec "$@"
