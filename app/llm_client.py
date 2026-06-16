"""LLM client implementations: OpenAI production client + deterministic mock."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)
from openai import OpenAIError

from app.config import settings
from app.exceptions import QuizGenerationError
from app.prompts import SYSTEM_PROMPT, build_user_prompt
from app.schemas import Quiz, TokenUsage


class LLMResponse:
    """Normalised LLM response."""

    def __init__(self, content: dict[str, Any], usage: TokenUsage) -> None:
        self.content = content
        self.usage = usage


class LLMClient(ABC):
    """Abstract LLM client."""

    @abstractmethod
    async def generate(
        self,
        sport: str,
        subject: str,
        grade_level: str,
        history_concepts: list[str],
        previous_error: str | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        """Generate a quiz payload."""


class OpenAILLMClient(LLMClient):
    """Production client using OpenAI's JSON mode."""

    def __init__(self, api_key: str | None = None) -> None:
        self.client = AsyncOpenAI(
            api_key=api_key or settings.openai_api_key,
            timeout=30.0,
            max_retries=0,  # retry logic lives in the pipeline
        )

    async def generate(
        self,
        sport: str,
        subject: str,
        grade_level: str,
        history_concepts: list[str],
        previous_error: str | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        model = model or settings.llm_primary_model
        user_prompt = build_user_prompt(
            sport=sport,
            subject=subject,
            grade_level=grade_level,
            history_concepts=history_concepts,
            previous_error=previous_error,
        )

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                response_format={"type": "json_object"},
            )
        except AuthenticationError as exc:
            raise QuizGenerationError(
                f"OpenAI authentication failed: {exc}", retryable=False
            ) from exc
        except BadRequestError as exc:
            raise QuizGenerationError(
                f"OpenAI bad request: {exc}", retryable=False
            ) from exc
        except (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError) as exc:
            raise QuizGenerationError(
                f"OpenAI transient error ({type(exc).__name__}): {exc}", retryable=True
            ) from exc
        except OpenAIError as exc:
            raise QuizGenerationError(
                f"OpenAI error: {exc}", retryable=True
            ) from exc

        raw_message = response.choices[0].message.content or "{}"
        try:
            content = json.loads(raw_message)
        except json.JSONDecodeError as exc:
            raise QuizGenerationError(
                f"OpenAI returned invalid JSON: {exc}", retryable=True
            ) from exc

        usage = TokenUsage(
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            model=model,
        )
        return LLMResponse(content=content, usage=usage)


class MockLLMClient(LLMClient):
    """Deterministic mock client for tests and local demos without API costs."""

    # Class-level hook for failure injection in tests.
    fail_next_n: int = 0
    failure_mode: str = "invalid_json"  # "invalid_json" | "schema_error"

    async def generate(
        self,
        sport: str,
        subject: str,
        grade_level: str,
        history_concepts: list[str],
        previous_error: str | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        if MockLLMClient.fail_next_n > 0:
            MockLLMClient.fail_next_n -= 1
            return self._failure_response(model or settings.llm_primary_model)

        # Pick fresh concepts not in history.
        base_concepts = [
            f"{sport} concept one",
            f"{sport} concept two",
            f"{sport} concept three",
            f"{subject} principle",
            f"applied {sport} analysis",
            f"{grade_level} level reasoning",
        ]
        fresh = [c for c in base_concepts if c not in history_concepts]
        if len(fresh) < 3:
            fresh = [f"unique concept {i}" for i in range(3)]

        quiz = {
            "quiz_id": str(uuid4()),
            "sport": sport,
            "subject": subject,
            "grade_level": grade_level,
            "questions": [
                {
                    "id": 1,
                    "difficulty": "easy",
                    "question": f"Easy {subject} question about {sport} for {grade_level} students.",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "A",
                    "explanation": f"This is the easy explanation covering {fresh[0]}.",
                    "concept": fresh[0],
                },
                {
                    "id": 2,
                    "difficulty": "medium",
                    "question": f"Medium {subject} question about {sport} for {grade_level} students.",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "B",
                    "explanation": f"This is the medium explanation covering {fresh[1]}.",
                    "concept": fresh[1],
                },
                {
                    "id": 3,
                    "difficulty": "hard",
                    "question": f"Hard {subject} question about {sport} for {grade_level} students.",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "C",
                    "explanation": f"This is the hard explanation covering {fresh[2]}.",
                    "concept": fresh[2],
                },
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        usage = TokenUsage(
            prompt_tokens=350,
            completion_tokens=450,
            model=model or settings.llm_primary_model,
        )
        return LLMResponse(content=quiz, usage=usage)

    def _failure_response(self, model: str) -> LLMResponse:
        if MockLLMClient.failure_mode == "invalid_json":
            content = {"raw": "this is not valid json"}  # Actually valid dict; force string below
            content = "this is not valid json"  # type: ignore[assignment]
        else:
            content = {
                "quiz_id": str(uuid4()),
                "sport": "baseball",
                "subject": "physics",
                "grade_level": "secondary",
                "questions": [
                    {
                        "id": 1,
                        "difficulty": "easy",
                        "question": "q1",
                        "options": ["A", "B"],
                        "correct_answer": "Z",
                        "explanation": "short",
                        "concept": "c",
                    }
                ],
            }
        return LLMResponse(
            content=content,  # type: ignore[arg-type]
            usage=TokenUsage(prompt_tokens=100, completion_tokens=100, model=model),
        )


def get_llm_client() -> LLMClient:
    """Return the configured LLM client."""
    if settings.use_mock_llm:
        return MockLLMClient()
    return OpenAILLMClient()
