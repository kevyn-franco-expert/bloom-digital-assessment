# Stage 1 — System Design

This document answers the five system-design questions for the Sports-Based Educational Quiz System.

---

## Question 1 — Complete System Architecture

### End-to-end data flow

```text
┌─────────────┐     POST /quizzes     ┌──────────────────────────────────────┐
│   Client    │ ─────────────────────▶│           FastAPI app                │
│  (web/app)  │                       │  · validation · rate limiting ·      │
└─────────────┘                       │    pipeline orchestration            │
                                      └──────────────┬───────────────────────┘
                                                     │
                          ┌──────────────────────────┼──────────────────────────┐
                          │                          │                          │
                          ▼                          ▼                          ▼
                   ┌─────────────┐          ┌──────────────┐          ┌──────────────┐
                   │   Redis     │          │   Postgres   │          │   OpenAI     │
                   │  (cache /   │          │  (quiz +     │          │  (primary    │
                   │  rate limit)│          │  student     │          │  model)      │
                   └─────────────┘          │  history)    │          └──────────────┘
                                            └──────────────┘                  │
                                                                              │
                                                                     fallback to gpt-4o
                                                                     if gpt-4o-mini fails
```

### Layers

| Layer | Responsibility | Technology |
|---|---|---|
| **Input** | Accept quiz requests, validate payload, authenticate | FastAPI + Pydantic |
| **Orchestration** | Memory lookup → LLM call → validation → retry → persistence → metrics | Python async pipeline |
| **Storage** | Student history, generated quizzes, operational events | PostgreSQL + SQLAlchemy |
| **Cache / Rate limit** | Session state, rate limits, request deduplication | Redis + in-memory fallback |
| **Output** | Return parseable JSON quiz to caller | FastAPI response model |
| **Monitoring** | Structured logs, latency/cost metrics, health checks | structlog + /health + stdout metrics |
| **Resilience** | Stop hammering OpenAI during outages | Circuit breaker |

### Scaling
- **Horizontal:** FastAPI is stateless; run multiple containers behind a load balancer.
- **Database:** read replicas for history lookups; connection pooling via asyncpg.
- **Rate limiting:** Redis-backed sliding-window limiter per `student_id` (10 req/min), with in-memory fallback for local dev.
- **Circuit breaker:** opens after 5 consecutive OpenAI failures, half-opens after 30s to avoid cascading outages.
- **Cost:** smaller model (`gpt-4o-mini`) first, fallback to `gpt-4o` only after retries.

---

## Question 2 — LLM Selection & Justification

### Primary model: `gpt-4o-mini`
- **Capabilities:** strong reasoning, fast, reliable JSON-mode output, excellent instruction following.
- **Cost:** ~15× cheaper than `gpt-4o` for this token volume.
- **Latency:** low enough for interactive quiz generation (~1–2s).
- **Availability:** OpenAI production API with high uptime.

### Fallback model: `gpt-4o`
- Used only when `gpt-4o-mini` fails validation after retries.
- More capable for edge-case physics/mathematics reasoning.

### Sub-task models
A separate classifier is unnecessary because the input domain is fixed (`sport` + `subject` + `grade_level`). If the system later adds content moderation, a smaller classifier (`gpt-4o-mini` itself) could screen for inappropriate content before returning a quiz.

### Fallback strategy
1. Retry `gpt-4o-mini` up to 3 times with exponential backoff.
2. If retries are exhausted, call `gpt-4o` once.
3. If `gpt-4o` also fails, raise `QuizGenerationError` and return a user-friendly 500.

### Trade-offs
| Model | Cost | Quality | Latency | Use case |
|---|---|---|---|---|
| GPT-4o-mini | Low | Good | Fast | Primary generation |
| GPT-4o | High | Best | Moderate | Fallback |
| Claude Sonnet | High | Excellent | Moderate | Good alternative, less native JSON schema |
| Gemini Pro | Medium | Good | Variable | Viable, provider lock-in |
| Llama 3 (self-hosted) | Infrastructure | Good | Depends | Avoids API costs, adds ops burden |

### Fine-tuning vs prompt engineering
- **Start with prompt engineering** (current approach). It is faster, cheaper, and easier to iterate.
- **Fine-tune** only after collecting thousands of labelled quizzes showing consistent patterns (e.g., district-specific curriculum, age-appropriate language). Fine-tuning is justified when prompt engineering cannot reach the required quality or when cost/latency must be reduced for a very stable task.

---

## Question 3 — Memory Between Sessions

### Storage backend: PostgreSQL + Redis
- **PostgreSQL:** durable, transactional, supports JSON columns for quiz/history storage. Ideal for the canonical record of every student.
- **Redis:** ephemeral cache for sessions, rate limits, and hot history windows. Optional for the core memory feature.

### Data persisted per student
```text
student_id (PK)
concepts     — last N concepts used (JSON array)
quiz_ids     — last N quiz IDs (JSON array)
updated_at
```

Only concept tags and quiz IDs are injected into prompts, not full PII. Scores could be added later to enable adaptive difficulty.

### Retrieval and injection
1. Query `student_history` by `student_id`.
2. Take the last `HISTORY_WINDOW_SIZE` concepts.
3. Format as: `Previously used concepts (do NOT reuse these): gravity, kinetic energy, ...`
4. Append to the user prompt.

### Expiry / cleanup
- History window is capped at `HISTORY_WINDOW_SIZE` per row (default 10).
- A nightly job can archive older records to cold storage for analytics.
- Quiz records can be soft-deleted after a retention policy (e.g., 3 years for student data).

### Privacy considerations
- No free-text student answers are stored unless explicitly required.
- `student_id` should be a pseudonym; map to real identity in a separate, access-controlled identity service.
- Encrypt data at rest (Postgres TDE or volume encryption).
- Return only the current student's data; validate auth tokens/headers.
- Comply with COPPA/FERPA depending on jurisdiction.

---

## Question 4 — Structured & Consistent Output

To guarantee parseable JSON from a probabilistic LLM, we use a layered defense:

1. **OpenAI JSON mode** (`response_format={"type": "json_object"}`) forces valid JSON.
2. **Pydantic schema** is enforced after every LLM call.
3. **Field-level pre-checks** catch missing keys, wrong option counts, and invalid `correct_answer` before Pydantic runs.
4. **Few-shot example** in the system prompt shows the exact expected structure.
5. **Retry with error injection:** if validation fails, the previous error is appended to the prompt for self-correction.
6. **Output normalisation:** `generated_at` is defaulted server-side if missing.

---

## Question 5 — Handling Invalid or Failed LLM Responses

### Error spectrum and handling

| Failure | Trigger | Recovery |
|---|---|---|
| **Invalid JSON** | LLM emits prose or truncated output | Retry with `Fix the JSON` instruction |
| **Schema mismatch** | Wrong question count, missing fields, bad difficulty order | Retry; inject validation error |
| **Off-topic content** | LLM ignores sport/subject pairing | Retry; reinforce topic constraints |
| **Rate limit / timeout** | OpenAI 429 or >30s | Exponential backoff (1s → 2s → 4s) |
| **Auth / bad request** | Invalid API key or malformed request | Fail fast (non-retryable) |
| **Cascading failure** | All retries + fallback exhausted | Raise `QuizGenerationError`, alert, return 500 |

### Retry policy
- Max retries: **3**.
- Back-off: **1s → 2s → 4s**.
- Fallback model used on the final attempt.
- Each retry logs the reason and previous error.

### Operational safeguards
- **Circuit breaker:** implemented in `app/circuit_breaker.py`. Opens after 5 consecutive failures and enters half-open state after 30s to probe recovery.
- **Rate limiting:** implemented in `app/rate_limit.py`. Sliding-window limit per student (10 req/min) using Redis sorted sets, with in-memory fallback.
- **Structured metrics:** every run emits `total_latency_ms`, `llm_latency_ms`, `prompt_tokens`, `completion_tokens`, `estimated_cost_usd`, `retry_count`, `validation_passed`, `student_id`, `sport`, `subject`.
- **Alerting:** high `retry_count` or failure rate triggers an alert (e.g., PagerDuty / Slack webhook).
