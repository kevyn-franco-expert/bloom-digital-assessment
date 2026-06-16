"""SQLAlchemy ORM models for quiz history and persistence."""
from datetime import datetime, timezone

from sqlalchemy import JSON, String, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class StudentHistory(Base):
    """Tracks concepts and recent quizzes per student to avoid repetition."""

    __tablename__ = "student_history"

    student_id: Mapped[str] = mapped_column(String, primary_key=True)
    concepts: Mapped[list[str]] = mapped_column(JSON, default=list)
    quiz_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class GeneratedQuiz(Base):
    """Stores full validated quizzes for audit and analytics."""

    __tablename__ = "generated_quizzes"

    quiz_id: Mapped[str] = mapped_column(String, primary_key=True)
    student_id: Mapped[str] = mapped_column(String, index=True)
    sport: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    grade_level: Mapped[str] = mapped_column(String)
    quiz_data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
