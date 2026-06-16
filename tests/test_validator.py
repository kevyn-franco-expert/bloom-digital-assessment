"""Tests for the schema validator."""
import copy
import json

import pytest

from app.exceptions import QuizGenerationError
from app.validator import validate_quiz_dict


VALID_QUIZ = {
    "quiz_id": "q1",
    "sport": "baseball",
    "subject": "physics",
    "grade_level": "secondary",
    "questions": [
        {
            "id": 1,
            "difficulty": "easy",
            "question": "Easy question?",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
            "explanation": "Because A is correct.",
            "concept": "gravity",
        },
        {
            "id": 2,
            "difficulty": "medium",
            "question": "Medium question?",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "B",
            "explanation": "Because B is correct.",
            "concept": "kinetic energy",
        },
        {
            "id": 3,
            "difficulty": "hard",
            "question": "Hard question?",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "C",
            "explanation": "Because C is correct.",
            "concept": "magnus effect",
        },
    ],
    "generated_at": "2026-06-15T12:00:00Z",
}


def test_validate_valid_quiz():
    result = validate_quiz_dict(VALID_QUIZ)
    assert result["sport"] == "baseball"
    assert len(result["questions"]) == 3


def test_validate_valid_json_string():
    result = validate_quiz_dict(json.dumps(VALID_QUIZ))
    assert result["quiz_id"] == "q1"


def test_validate_invalid_json():
    with pytest.raises(QuizGenerationError) as exc_info:
        validate_quiz_dict("not json")
    assert exc_info.value.retryable


def test_validate_missing_questions():
    data = {**VALID_QUIZ, "questions": []}
    with pytest.raises(QuizGenerationError) as exc_info:
        validate_quiz_dict(data)
    assert "exactly 3" in str(exc_info.value)


def test_validate_wrong_difficulty_order():
    data = copy.deepcopy(VALID_QUIZ)
    data["questions"][0]["difficulty"] = "hard"
    data["questions"][2]["difficulty"] = "easy"
    with pytest.raises(QuizGenerationError):
        validate_quiz_dict(data)


def test_validate_missing_fields():
    data = copy.deepcopy(VALID_QUIZ)
    del data["questions"][0]["explanation"]
    with pytest.raises(QuizGenerationError) as exc_info:
        validate_quiz_dict(data)
    assert "missing required fields" in str(exc_info.value)


def test_validate_correct_answer_not_in_options():
    data = copy.deepcopy(VALID_QUIZ)
    data["questions"][0]["correct_answer"] = "Z"
    with pytest.raises(QuizGenerationError) as exc_info:
        validate_quiz_dict(data)
    assert "not one of the options" in str(exc_info.value)


def test_validate_wrong_options_count():
    data = copy.deepcopy(VALID_QUIZ)
    data["questions"][1]["options"] = ["A", "B"]
    with pytest.raises(QuizGenerationError):
        validate_quiz_dict(data)
