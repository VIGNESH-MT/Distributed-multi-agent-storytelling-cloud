import pytest
from pydantic import ValidationError

from app.agents.provenance import (
    create_agent_execution_trace,
    execute_agent_with_trace,
)
from app.core.config import get_model_settings


def test_mock_execution_has_no_model():
    trace = create_agent_execution_trace(
        agent="character",
        provider="mock",
        execution_location="local",
        duration_ms=12.5,
    )

    assert trace.provider == "mock"
    assert trace.model is None
    assert trace.execution_location == "local"
    assert trace.duration_ms == 12.5


def test_gemini_execution_records_configured_model(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    get_model_settings.cache_clear()

    try:
        trace = create_agent_execution_trace(
            agent="plot",
            provider="gemini",
            execution_location="remote",
            duration_ms=25.0,
        )

        assert trace.provider == "gemini"
        assert trace.model == "gemini-test-model"
        assert trace.execution_location == "remote"
    finally:
        get_model_settings.cache_clear()


def test_unsupported_provider_is_rejected():
    with pytest.raises(ValueError, match="Provider"):
        create_agent_execution_trace(
            agent="critic",
            provider="unknown",
            execution_location="local",
            duration_ms=10.0,
        )


def test_negative_duration_is_rejected():
    with pytest.raises(ValidationError):
        create_agent_execution_trace(
            agent="critic",
            provider="mock",
            execution_location="local",
            duration_ms=-1.0,
        )


def test_execution_wrapper_returns_result_and_measured_trace():
    result, trace = execute_agent_with_trace(
        agent="plot",
        provider="mock",
        execution_location="local",
        operation=lambda: {"proposal": "test"},
    )

    assert result == {"proposal": "test"}
    assert trace.agent == "plot"
    assert trace.provider == "mock"
    assert trace.model is None
    assert trace.execution_location == "local"
    assert trace.duration_ms >= 0


def test_execution_wrapper_propagates_agent_failure():
    def failing_operation():
        raise RuntimeError("Simulated agent failure")

    with pytest.raises(RuntimeError, match="Simulated agent failure"):
        execute_agent_with_trace(
            agent="critic",
            provider="mock",
            execution_location="local",
            operation=failing_operation,
        )
