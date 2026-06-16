"""Application configuration loaded from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised, type-safe configuration.

    Values are read from a `.env` file and environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"

    # OpenAI
    openai_api_key: str
    llm_primary_model: str = "gpt-4o-mini"
    llm_fallback_model: str = "gpt-4o"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 2000

    # Retry behaviour
    llm_max_retries: int = 3
    llm_retry_base_delay: float = 1.0

    # Memory
    history_window_size: int = 10

    # Infrastructure
    database_url: str = "sqlite+aiosqlite:///./quiz_local.db"
    redis_url: str | None = None

    # Feature flags
    use_mock_llm: bool = False

    @property
    def is_testing(self) -> bool:
        return self.app_env.lower() == "testing"


settings = Settings()
