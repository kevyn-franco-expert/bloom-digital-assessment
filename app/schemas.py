"""Pydantic schemas for requests, responses, and structured LLM output."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class Question(BaseModel):
    """A single multiple-choice question."""

    id: int = Field(..., ge=1, description="1-based question index")
    difficulty: Literal["easy", "medium", "hard"]
    question: str = Field(..., min_length=5)
    options: list[str] = Field(..., min_length=4, max_length=4)
    correct_answer: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=10)
    concept: str = Field(..., min_length=2)

    @field_validator("correct_answer")
    @classmethod
    def correct_answer_must_be_an_option(cls, value: str, info) -> str:
        options = info.data.get("options") or []
        if options and value not in options:
            raise ValueError("correct_answer must be one of the provided options")
        return value


class Quiz(BaseModel):
    """Structured quiz returned by the LLM and by the API."""

    quiz_id: str = Field(default_factory=lambda: str(uuid4()))
    sport: str
    subject: str
    grade_level: str
    questions: list[Question]
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("questions")
    @classmethod
    def exactly_three_increasing_difficulty(cls, questions: list[Question]) -> list[Question]:
        if len(questions) != 3:
            raise ValueError(f"expected exactly 3 questions, got {len(questions)}")
        expected = ["easy", "medium", "hard"]
        for i, q in enumerate(questions):
            if q.difficulty != expected[i]:
                raise ValueError(
                    f"question {i + 1} difficulty must be '{expected[i]}', got '{q.difficulty}'"
                )
            if q.id != i + 1:
                raise ValueError(
                    f"question ids must be 1,2,3 in order; got id={q.id} at position {i + 1}"
                )
        return questions


class QuizRequest(BaseModel):
    """API request body."""

    sport: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    grade_level: str = Field(..., pattern="^(elementary|secondary)$")
    student_id: str = Field(..., min_length=1)


class QuizResponse(Quiz):
    """Response model exposed by the API."""
    pass


class TokenUsage(BaseModel):
    """Token usage metadata returned by an LLM call."""

    prompt_tokens: int
    completion_tokens: int
    model: str
