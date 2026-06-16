"""Stage 2 standalone quiz generation function.

This module isolates the core generation + validation behaviour so it can be
imported and tested independently of the full pipeline, persistence, and API.
"""
from app.config import settings
from app.exceptions import QuizGenerationError
from app.llm_client import LLMClient, OpenAILLMClient
from app.prompts import build_user_prompt
from app.validator import validate_quiz_dict


async def generar_quiz(
    sport: str,
    subject: str,
    grade_level: str,
    student_id: str,
    *,
    llm_client: LLMClient | None = None,
    history_concepts: list[str] | None = None,
) -> dict:
    """Generate an educational quiz and return a validated dict.

    Args:
        sport: Sport context, e.g. "baseball".
        subject: Academic subject, e.g. "physics".
        grade_level: "elementary" or "secondary".
        student_id: Identifier for the student (used only for logging here).
        llm_client: Optional LLM client override for testing.
        history_concepts: Optional list of concepts to avoid repeating.

    Returns:
        A dict matching the required quiz JSON schema.

    Raises:
        QuizGenerationError: If the LLM output cannot be validated.
    """
    client = llm_client or OpenAILLMClient()
    history_concepts = history_concepts or []

    response = await client.generate(
        sport=sport,
        subject=subject,
        grade_level=grade_level,
        history_concepts=history_concepts,
    )

    try:
        validated = validate_quiz_dict(
            response.content, model_used=response.usage.model
        )
    except QuizGenerationError:
        raise
    except Exception as exc:
        raise QuizGenerationError(
            f"Unexpected validation error: {exc}", retryable=True
        ) from exc

    return validated
