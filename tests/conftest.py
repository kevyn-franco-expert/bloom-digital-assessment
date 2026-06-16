"""Shared test fixtures and configuration."""
import os

# Configure the test environment BEFORE any app modules are imported.
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_quiz.db")
os.environ.setdefault("USE_MOCK_LLM", "true")
os.environ.setdefault("LLM_MAX_RETRIES", "2")
os.environ.setdefault("LLM_RETRY_BASE_DELAY", "0.0")
os.environ.setdefault("REDIS_URL", "")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app import dependencies
from app.config import settings
from app.dependencies import get_db
from app.main import app
from app.models import Base


test_engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)

test_session_factory = sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def override_get_db():
    async with test_session_factory() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
async def reset_mock_llm():
    """Ensure the mock LLM does not carry failure state between tests."""
    from app.llm_client import MockLLMClient

    MockLLMClient.fail_next_n = 0
    MockLLMClient.failure_mode = "invalid_json"
    yield
    MockLLMClient.fail_next_n = 0


@pytest.fixture(autouse=True)
async def reset_rate_limiter_and_breaker():
    from app.circuit_breaker import get_default_breaker
    from app.rate_limit import get_default_limiter

    limiter = get_default_limiter()
    breaker = get_default_breaker()
    await limiter.reset()
    await breaker.reset()
    yield
    await limiter.reset()
    await breaker.reset()


@pytest.fixture(autouse=True)
async def setup_database():
    """Create tables before and drop them after each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Override app engine so the lifespan and endpoints use the test DB.
    original_engine = dependencies.engine
    original_factory = dependencies.async_session_factory
    dependencies.engine = test_engine
    dependencies.async_session_factory = test_session_factory
    yield
    dependencies.engine = original_engine
    dependencies.async_session_factory = original_factory
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def db_session():
    async with test_session_factory() as session:
        yield session
