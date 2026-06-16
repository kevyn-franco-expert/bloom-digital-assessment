"""Tests for the Stage 2 generar_quiz() function."""
import pytest

from app.generation import generar_quiz
from app.llm_client import MockLLMClient


@pytest.mark.asyncio
async def test_generar_quiz_returns_valid_dict():
    result = await generar_quiz(
        sport="baseball",
        subject="physics",
        grade_level="secondary",
        student_id="stu-001",
        llm_client=MockLLMClient(),
    )
    assert result["sport"] == "baseball"
    assert result["subject"] == "physics"
    assert len(result["questions"]) == 3
    assert [q["difficulty"] for q in result["questions"]] == ["easy", "medium", "hard"]


@pytest.mark.asyncio
async def test_generar_quiz_avoids_history_concepts():
    client = MockLLMClient()
    history = ["baseball concept one", "baseball concept two"]
    result = await generar_quiz(
        sport="baseball",
        subject="physics",
        grade_level="secondary",
        student_id="stu-001",
        llm_client=client,
        history_concepts=history,
    )
    concepts = {q["concept"] for q in result["questions"]}
    assert not concepts.intersection(set(history))
