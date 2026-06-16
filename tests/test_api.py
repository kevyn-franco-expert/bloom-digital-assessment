"""Tests for the FastAPI endpoints."""
import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_create_quiz(client):
    payload = {
        "sport": "baseball",
        "subject": "physics",
        "grade_level": "secondary",
        "student_id": "stu-api-001",
    }
    response = await client.post("/quizzes", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["sport"] == "baseball"
    assert data["subject"] == "physics"
    assert len(data["questions"]) == 3
    assert [q["difficulty"] for q in data["questions"]] == ["easy", "medium", "hard"]


@pytest.mark.asyncio
async def test_create_quiz_invalid_grade(client):
    payload = {
        "sport": "baseball",
        "subject": "physics",
        "grade_level": "university",
        "student_id": "stu-api-002",
    }
    response = await client.post("/quizzes", json=payload)
    assert response.status_code == 422
