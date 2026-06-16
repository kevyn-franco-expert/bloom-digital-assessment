"""Tests for the full Stage 3 pipeline."""
import pytest
from sqlalchemy import select

from app.exceptions import QuizGenerationError
from app.llm_client import MockLLMClient
from app.memory import get_history_context
from app.models import GeneratedQuiz
from app.pipeline import generate_quiz_pipeline


@pytest.mark.asyncio
async def test_pipeline_generates_and_persists_quiz(db_session):
    client = MockLLMClient()
    quiz = await generate_quiz_pipeline(
        sport="baseball",
        subject="physics",
        grade_level="secondary",
        student_id="stu-pipe-001",
        db=db_session,
        llm_client=client,
    )
    assert quiz["sport"] == "baseball"
    assert len(quiz["questions"]) == 3

    history_concepts, _ = await get_history_context(db_session, "stu-pipe-001")
    assert len(history_concepts) == 3

    result = await db_session.execute(
        select(GeneratedQuiz).where(GeneratedQuiz.student_id == "stu-pipe-001")
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_pipeline_retries_then_succeeds(db_session):
    client = MockLLMClient()
    MockLLMClient.fail_next_n = 1  # first call returns bad JSON
    MockLLMClient.failure_mode = "invalid_json"

    quiz = await generate_quiz_pipeline(
        sport="american football",
        subject="mathematics",
        grade_level="elementary",
        student_id="stu-pipe-002",
        db=db_session,
        llm_client=client,
    )
    assert len(quiz["questions"]) == 3


@pytest.mark.asyncio
async def test_pipeline_fails_after_retries(db_session):
    client = MockLLMClient()
    MockLLMClient.fail_next_n = 10  # always fail
    MockLLMClient.failure_mode = "invalid_json"

    with pytest.raises(QuizGenerationError):
        await generate_quiz_pipeline(
            sport="baseball",
            subject="physics",
            grade_level="secondary",
            student_id="stu-pipe-003",
            db=db_session,
            llm_client=client,
        )


@pytest.mark.asyncio
async def test_pipeline_avoids_repeating_concepts(db_session):
    client = MockLLMClient()
    # First quiz seeds history.
    quiz1 = await generate_quiz_pipeline(
        sport="baseball",
        subject="physics",
        grade_level="secondary",
        student_id="stu-pipe-004",
        db=db_session,
        llm_client=client,
    )
    concepts1 = [q["concept"] for q in quiz1["questions"]]

    quiz2 = await generate_quiz_pipeline(
        sport="baseball",
        subject="physics",
        grade_level="secondary",
        student_id="stu-pipe-004",
        db=db_session,
        llm_client=client,
    )
    concepts2 = [q["concept"] for q in quiz2["questions"]]

    # The mock LLM explicitly avoids concepts it knows about.
    assert not set(concepts1).intersection(set(concepts2))
