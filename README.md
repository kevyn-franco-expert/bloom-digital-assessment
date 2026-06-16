# Sports-Based Educational Quiz System

A production-oriented LLM pipeline that generates academic quizzes contextualised in sports for elementary and secondary students.

## What this project delivers

- **Stage 1 — Diseño:** `docs/ARCHITECTURE.md` con respuestas a las 5 preguntas de arquitectura.
- **Stage 2 — Prompt Engineering:** función `generar_quiz()` en `app/generation.py`, prompts separados system/user, few-shot example, manejo de errores y JSON validado.
- **Stage 3 — Pipeline completo:** `app/pipeline.py` con memoria, LLM, validación, retry exponencial (1s→2s→4s), persistencia en Postgres/SQLite y métricas estructuradas.
- **Producción lista:**
  - **Rate limiting** por estudiante (Redis con fallback en memoria) en `app/rate_limit.py`.
  - **Circuit breaker** para OpenAI en `app/circuit_breaker.py`.
- **API:** FastAPI en `app/main.py` con `POST /quizzes` y `GET /health`.
- **Docker:** `Dockerfile`, `docker-compose.yml` (app, Postgres, Redis) validado en Docker Desktop.
- **Tests:** 22 pruebas con pytest (validador, generación, pipeline, retry, API, rate limit, circuit breaker).

## Project structure

```text
bloom-digital-assessment/
├── app/                    # Application source
│   ├── main.py             # FastAPI app
│   ├── pipeline.py         # End-to-end generation pipeline
│   ├── generation.py       # Stage 2 generar_quiz()
│   ├── llm_client.py       # OpenAI + mock LLM clients
│   ├── validator.py        # Schema validation
│   ├── memory.py           # Student history lookup/upsert
│   ├── metrics.py          # Cost estimation + structured logging
│   ├── rate_limit.py       # Redis/in-memory rate limiter
│   ├── circuit_breaker.py  # Circuit breaker for OpenAI
│   ├── prompts.py          # System/user prompt templates
│   ├── schemas.py          # Pydantic models
│   ├── models.py           # SQLAlchemy tables
│   ├── dependencies.py     # DB/Redis lifespan + FastAPI deps
│   └── config.py           # Settings
├── tests/                  # pytest suite
├── docs/ARCHITECTURE.md    # Stage 1 design answers
├── docker/                 # Dockerfile + entrypoint
├── docker-compose.yml      # Full Docker stack
├── pyproject.toml          # Dependencies
└── .env                    # Local secrets (gitignored)
```

## Quick start (local, no Docker)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v                    # 22 tests
uvicorn app.main:app --reload # servidor local
```

By default tests and local runs use the deterministic mock LLM via `USE_MOCK_LLM=true`.

## Docker Compose (validated on Docker Desktop)

```bash
# La app lee OPENAI_API_KEY desde .env
docker compose --env-file .env up --build -d

# Health check
curl http://localhost:8000/health

# Generate a real quiz via OpenAI
curl -X POST http://localhost:8000/quizzes \
  -H "Content-Type: application/json" \
  -d '{"sport":"baseball","subject":"physics","grade_level":"secondary","student_id":"stu-001"}'

# Run the full test suite inside a container (mock LLM, no API cost)
docker compose --profile test run --rm --build test
```

## Key design decisions

- **OpenAI JSON mode + Pydantic validation** gives strong output guarantees.
- **Retry loop** with exponential backoff (1s → 2s → 4s) and fallback to `gpt-4o`.
- **Circuit breaker** opens after 5 consecutive OpenAI failures and half-opens after 30s.
- **Rate limiting** per `student_id` (10 requests/minute), backed by Redis in Docker or in-memory locally.
- **Deterministic mock LLM** makes tests fast, cheap, and repeatable.
- **Postgres + Redis** in Docker for real persistence and caching; SQLite fallback for local development.
- **Structured metrics** emitted for every pipeline run (latency, tokens, cost, retries, validation status).

## Security note

The OpenAI API key is stored only in `.env` and excluded from Git. Because it was shared in chat, **rotate it after this demo**.
