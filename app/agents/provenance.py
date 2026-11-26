"""Validated execution provenance for storytelling agents."""

import time
from collections.abc import Callable
from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_model_settings


AgentName = Literal["plot", "character", "critic"]
AgentProvider = Literal["mock", "gemini"]
ExecutionLocation = Literal["local", "remote"]

T = TypeVar("T")


class AgentExecutionTrace(BaseModel):
    """Auditable metadata for one agent execution."""

    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    provider: AgentProvider
    model: str | None
    execution_location: ExecutionLocation
    duration_ms: float = Field(ge=0)


def create_agent_execution_trace(
    *,
    agent: AgentName,
    provider: AgentProvider,
    execution_location: ExecutionLocation,
    duration_ms: float,
) -> AgentExecutionTrace:
    """Construct a trace using the provider that actually executed."""

    if provider not in {"mock", "gemini"}:
        raise ValueError(
            "Provider must be either 'mock' or 'gemini'."
        )

    model = None

    if provider == "gemini":
        model = get_model_settings().gemini_model

    return AgentExecutionTrace(
        agent=agent,
        provider=provider,
        model=model,
        execution_location=execution_location,
        duration_ms=duration_ms,
    )


def execute_agent_with_trace(
    *,
    agent: AgentName,
    provider: AgentProvider,
    execution_location: ExecutionLocation,
    operation: Callable[[], T],
) -> tuple[T, AgentExecutionTrace]:
    """Execute an agent operation and measure its wall-clock duration."""

    start_time = time.perf_counter()
    result = operation()
    duration_ms = (time.perf_counter() - start_time) * 1000

    trace = create_agent_execution_trace(
        agent=agent,
        provider=provider,
        execution_location=execution_location,
        duration_ms=duration_ms,
    )

    return result, trace
