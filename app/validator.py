"""Validate raw LLM output against the required quiz schema."""
import json
from typing import Any

from pydantic import ValidationError

from app.exceptions import QuizGenerationError
from app.schemas import Quiz


REQUIRED_QUESTION_FIELDS = {
    "id",
    "difficulty",
    "question",
    "options",
    "correct_answer",
    "explanation",
    "concept",
}


def validate_quiz_dict(raw: Any, *, model_used: str = "unknown") -> dict:
    """Validate that `raw` is parseable JSON and conforms to the Quiz schema.

    Returns the validated dict on success. Raises QuizGenerationError (retryable)
    on any failure so the pipeline can decide whether to retry.
    """
    # 1. Must be a dict or a JSON string.
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise QuizGenerationError(
                f"Invalid JSON returned by model {model_used}: {exc}",
                retryable=True,
            ) from exc
    elif isinstance(raw, dict):
        data = raw
    else:
        raise QuizGenerationError(
            f"Unexpected LLM output type from model {model_used}: {type(raw).__name__}",
            retryable=True,
        )

    # 2. Top-level structure checks.
    if not isinstance(data, dict):
        raise QuizGenerationError(
            f"LLM output is not a JSON object (model {model_used})",
            retryable=True,
        )

    if "questions" not in data:
        raise QuizGenerationError(
            "Missing 'questions' field in LLM output", retryable=True
        )

    questions = data.get("questions")
    if not isinstance(questions, list):
        raise QuizGenerationError(
            "'questions' must be a list", retryable=True
        )

    if len(questions) != 3:
        raise QuizGenerationError(
            f"Expected exactly 3 questions, got {len(questions)}", retryable=True
        )

    # 3. Per-question field checks before full Pydantic validation.
    for idx, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            raise QuizGenerationError(
                f"Question {idx} is not an object", retryable=True
            )
        missing = REQUIRED_QUESTION_FIELDS - question.keys()
        if missing:
            raise QuizGenerationError(
                f"Question {idx} missing required fields: {sorted(missing)}",
                retryable=True,
            )
        options = question.get("options")
        if not isinstance(options, list) or len(options) != 4:
            raise QuizGenerationError(
                f"Question {idx} must have exactly 4 options", retryable=True
            )
        correct = question.get("correct_answer")
        if correct not in options:
            raise QuizGenerationError(
                f"Question {idx} correct_answer '{correct}' is not one of the options",
                retryable=True,
            )

    # 4. Full Pydantic validation (catches difficulty progression, types, etc.).
    try:
        quiz = Quiz.model_validate(data)
    except ValidationError as exc:
        messages = "; ".join(
            f"{' -> '.join(str(loc) for loc in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        )
        raise QuizGenerationError(
            f"Schema validation failed: {messages}", retryable=True
        ) from exc

    # 5. Post-normalisation: ensure generated_at is present and quiz_id exists.
    validated = quiz.model_dump(mode="json")
    return validated
