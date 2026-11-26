"""Shared application setup for independent storytelling agent services."""

from collections.abc import Callable
from typing import Generic, TypeVar

from fastapi import FastAPI
from pydantic import BaseModel

from app.agents.provenance import (
    AgentExecutionTrace,
    AgentName,
    execute_agent_with_trace,
)
from app.agents.story_agents import AGENT_PROVIDER


ResultT = TypeVar("ResultT")


class AgentExecutionResponse(BaseModel, Generic[ResultT]):
    """Standard response envelope for an independent agent service."""

    result: ResultT
    trace: AgentExecutionTrace


def execute_remote_agent(
    *,
    agent: AgentName,
    operation: Callable[[], ResultT],
) -> AgentExecutionResponse[ResultT]:
    """Execute an agent and return its result with measured provenance."""

    result, trace = execute_agent_with_trace(
        agent=agent,
        provider=AGENT_PROVIDER,
        execution_location="remote",
        operation=operation,
    )

    return AgentExecutionResponse(
        result=result,
        trace=trace,
    )


def create_agent_app(service_name: str) -> FastAPI:
    app = FastAPI(
        title=service_name,
        description="Independent agent service for the distributed storytelling system.",
        version="0.1.0",
    )

    @app.get("/health/live")
    def liveness():
        return {"status": "alive", "service": service_name}

    @app.get("/health/ready")
    def readiness():
        return {"status": "ready", "service": service_name}

    return app
