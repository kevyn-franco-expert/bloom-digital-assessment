"""Student memory / history lookup and persistence."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import GeneratedQuiz, StudentHistory


async def get_history_context(
    db: AsyncSession,
    student_id: str,
) -> tuple[list[str], list[str]]:
    """Return (concepts, quiz_ids) for a student, bounded by HISTORY_WINDOW_SIZE.

    If the student has no history, returns two empty lists.
    """
    row = await db.get(StudentHistory, student_id)
    if row is None:
        return [], []
    window = settings.history_window_size
    concepts = (row.concepts or [])[-window:]
    quiz_ids = (row.quiz_ids or [])[-window:]
    return concepts, quiz_ids


async def record_quiz(
    db: AsyncSession,
    student_id: str,
    quiz: dict,
) -> None:
    """Persist the quiz and update the student's history atomically.

    This function performs all DB writes in the current session; the caller is
    responsible for committing the transaction.
    """
    quiz_id = quiz.get("quiz_id")
    concepts = [q.get("concept", "") for q in quiz.get("questions", [])]

    # 1. Save full quiz record.
    db.add(
        GeneratedQuiz(
            quiz_id=quiz_id,
            student_id=student_id,
            sport=quiz.get("sport"),
            subject=quiz.get("subject"),
            grade_level=quiz.get("grade_level"),
            quiz_data=quiz,
        )
    )

    # 2. Upsert student history.
    row = await db.get(StudentHistory, student_id)
    if row is None:
        row = StudentHistory(
            student_id=student_id,
            concepts=concepts,
            quiz_ids=[quiz_id],
        )
        db.add(row)
    else:
        row.concepts = (row.concepts or []) + concepts
        row.quiz_ids = (row.quiz_ids or []) + [quiz_id]

    # Trim to configured window to avoid unbounded growth.
    window = settings.history_window_size
    row.concepts = row.concepts[-window:]
    row.quiz_ids = row.quiz_ids[-window:]
