"""Stage 3 production pipeline: memory → generation → validation → retry → persistence → metrics."""
import asyncio
from time import perf_counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.circuit_breaker import get_default_breaker
from app.config import settings
from app.exceptions import QuizGenerationError
from app.llm_client import LLMClient, LLMResponse, get_llm_client
from app.memory import get_history_context, record_quiz
from app.metrics import PipelineMetrics, estimate_cost, log_metrics
from app.validator import validate_quiz_dict


async def generate_quiz_pipeline(
    sport: str,
    subject: str,
    grade_level: str,
    student_id: str,
    db: AsyncSession,
    *,
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """End-to-end pipeline that always returns a validated quiz dict.

    Steps:
        1. Look up student history.
        2. Call the LLM (with retry + error injection).
        3. Validate the structured output.
        4. Persist quiz + history.
        5. Log structured operational metrics.
    """
    client = llm_client or get_llm_client()
    total_start = perf_counter()

    history_concepts: list[str] = []
    quiz: dict[str, Any] | None = None
    retry_count = 0
    validation_passed = False
    previous_error: str | None = None
    last_exception: QuizGenerationError | None = None
    llm_latency_ms = 0.0
    prompt_tokens = 0
    completion_tokens = 0
    model_used = settings.llm_primary_model

    try:
        # Step 1: memory lookup.
        history_concepts, _ = await get_history_context(db, student_id)

        # Step 2-4: generation with validation and retry.
        max_retries = settings.llm_max_retries
        base_delay = settings.llm_retry_base_delay

        for attempt in range(max_retries + 1):
            model = settings.llm_primary_model
            if attempt == max_retries and max_retries > 0:
                # Final attempt uses the larger fallback model.
                model = settings.llm_fallback_model
            model_used = model

            llm_start = perf_counter()
            try:
                breaker = get_default_breaker()
                response: LLMResponse = await breaker.call(
                    client.generate(
                        sport=sport,
                        subject=subject,
                        grade_level=grade_level,
                        history_concepts=history_concepts,
                        previous_error=previous_error,
                        model=model,
                    )
                )
            except QuizGenerationError as exc:
                last_exception = exc
                if not exc.retryable or attempt == max_retries:
                    raise
                retry_count += 1
                previous_error = str(exc)
                await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
                continue
            except Exception as exc:
                # Any unexpected exception is wrapped as retryable.
                last_exception = QuizGenerationError(str(exc), retryable=True)
                if attempt == max_retries:
                    raise last_exception from exc
                retry_count += 1
                previous_error = str(exc)
                await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
                continue
            finally:
                llm_latency_ms = (perf_counter() - llm_start) * 1000

            # Validate.
            try:
                quiz = validate_quiz_dict(response.content, model_used=model)
            except QuizGenerationError as exc:
                last_exception = exc
                if not exc.retryable or attempt == max_retries:
                    raise
                retry_count += 1
                previous_error = str(exc)
                await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
                continue

            # Extract usage from the successful response.
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            validation_passed = True
            break

        if quiz is None:
            raise last_exception or QuizGenerationError(
                "Quiz generation failed after all retries", retryable=False
            )

        # Step 5: persistence.
        await record_quiz(db, student_id, quiz)
        await db.commit()

    except Exception:
        await db.rollback()
        raise
    finally:
        # Step 6: metrics logging — always emitted, even on failure.
        total_latency_ms = (perf_counter() - total_start) * 1000
        estimated_cost = estimate_cost(
            model_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        log_metrics(
            PipelineMetrics(
                total_latency_ms=total_latency_ms,
                llm_latency_ms=llm_latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                estimated_cost_usd=estimated_cost,
                retry_count=retry_count,
                validation_passed=validation_passed,
                student_id=student_id,
                sport=sport,
                subject=subject,
            )
        )

    return quiz
