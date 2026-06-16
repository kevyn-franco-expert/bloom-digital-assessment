"""FastAPI application exposing the quiz generation pipeline."""
from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, lifespan
from app.pipeline import generate_quiz_pipeline
from app.rate_limit import check_rate_limit
from app.schemas import QuizRequest, QuizResponse

app = FastAPI(
    title="Sports-Based Educational Quiz API",
    description="Generate academic quizzes contextualised in sports for K-12 students.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["health"])
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    """Verify the API and database are reachable."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unhealthy: {exc}",
        ) from exc


@app.post(
    "/quizzes",
    response_model=QuizResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["quizzes"],
)
async def create_quiz(
    request: QuizRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a new personalised quiz for a student."""
    await check_rate_limit(request.student_id)
    try:
        quiz = await generate_quiz_pipeline(
            sport=request.sport,
            subject=request.subject,
            grade_level=request.grade_level,
            student_id=request.student_id,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quiz generation failed: {exc}",
        ) from exc
    return quiz
