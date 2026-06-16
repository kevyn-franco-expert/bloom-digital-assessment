"""Operational metrics and cost estimation."""
from dataclasses import dataclass
from decimal import Decimal

import structlog

logger = structlog.get_logger("quiz.metrics")


# Pricing in USD per 1M tokens (approximate OpenAI tier-1 rates).
MODEL_PRICING: dict[str, dict[str, Decimal]] = {
    "gpt-4o-mini": {
        "prompt": Decimal("0.15"),
        "completion": Decimal("0.60"),
    },
    "gpt-4o": {
        "prompt": Decimal("2.50"),
        "completion": Decimal("10.00"),
    },
}


@dataclass
class PipelineMetrics:
    """Metrics captured for every pipeline run."""

    total_latency_ms: float
    llm_latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    retry_count: int
    validation_passed: bool
    student_id: str
    sport: str
    subject: str


def estimate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Estimate API cost in USD."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-4o-mini"])
    cost = (
        Decimal(prompt_tokens) * pricing["prompt"]
        + Decimal(completion_tokens) * pricing["completion"]
    ) / Decimal("1_000_000")
    return float(cost)


def log_metrics(metrics: PipelineMetrics) -> None:
    """Emit structured metrics to the configured logger."""
    logger.info(
        "quiz_pipeline_completed",
        total_latency_ms=round(metrics.total_latency_ms, 3),
        llm_latency_ms=round(metrics.llm_latency_ms, 3),
        prompt_tokens=metrics.prompt_tokens,
        completion_tokens=metrics.completion_tokens,
        estimated_cost_usd=round(metrics.estimated_cost_usd, 6),
        retry_count=metrics.retry_count,
        validation_passed=metrics.validation_passed,
        student_id=metrics.student_id,
        sport=metrics.sport,
        subject=metrics.subject,
    )
