"""Domain-specific exceptions."""


class QuizGenerationError(Exception):
    """Raised when a quiz cannot be generated or validated."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable
