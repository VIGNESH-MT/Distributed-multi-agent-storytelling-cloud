import pytest
from fastapi.testclient import TestClient

import app.agent_services.common as common
import app.agent_services.plot as plot_service
import app.agent_services.character as character_service
import app.agent_services.critic as critic_service


plot_result = {
    "central_conflict": "A missing navigation chart threatens the expedition.",
    "proposed_events": [
        "Mira discovers a damaged chart.",
        "Elias identifies a hidden route.",
    ],
    "causal_logic": "The damaged chart forces the crew to investigate.",
    "unresolved_questions": ["Who altered the chart?"],
}

character_result = {
    "character_developments": ["Mira becomes more decisive."],
    "dialogue": ["Mira: We must follow the evidence."],
    "motivations": ["Mira wants to protect the expedition."],
    "proposed_story_continuation": (
        "Mira examined the chart and discovered a hidden passage."
    ),
}

critic_result = {
    "approved": True,
    "coherence_score": 90,
    "continuity_issues": [],
    "causal_issues": [],
    "revision_instructions": [],
    "explanation": "The proposed continuation is coherent and consistent.",
}

plot_payload = {
    "story_title": "The Hidden Passage",
    "current_story": "Mira and Elias are exploring an abandoned station.",
    "user_request": "Introduce a mysterious discovery.",
}

character_payload = {
    **plot_payload,
    "plot": plot_result,
    "revision_feedback": [],
}

critic_payload = {
    **plot_payload,
    "plot": plot_result,
    "character": character_result,
}


@pytest.mark.parametrize(
    "service,endpoint,payload,agent,result",
    [
        (
            plot_service,
            "/propose",
            plot_payload,
            "plot",
            plot_result,
        ),
        (
            character_service,
            "/propose",
            character_payload,
            "character",
            character_result,
        ),
        (
            critic_service,
            "/evaluate",
            critic_payload,
            "critic",
            critic_result,
        ),
    ],
)
def test_agent_endpoint_returns_result_and_remote_trace(
    monkeypatch,
    service,
    endpoint,
    payload,
    agent,
    result,
):
    monkeypatch.setattr(common, "AGENT_PROVIDER", "mock")

    operation_names = {
        "plot": "run_plot_agent",
        "character": "run_character_agent",
        "critic": "run_critic_agent",
    }

    monkeypatch.setattr(
        service,
        operation_names[agent],
        lambda **kwargs: result,
    )

    response = TestClient(service.app).post(
        endpoint,
        json=payload,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["result"] == result
    assert body["trace"]["agent"] == agent
    assert body["trace"]["provider"] == "mock"
    assert body["trace"]["model"] is None
    assert body["trace"]["execution_location"] == "remote"
    assert body["trace"]["duration_ms"] >= 0


@pytest.mark.parametrize(
    "service,endpoint,payload,operation_name",
    [
        (
            plot_service,
            "/propose",
            plot_payload,
            "run_plot_agent",
        ),
        (
            character_service,
            "/propose",
            character_payload,
            "run_character_agent",
        ),
        (
            critic_service,
            "/evaluate",
            critic_payload,
            "run_critic_agent",
        ),
    ],
)
def test_agent_endpoint_returns_502_on_execution_failure(
    service,
    endpoint,
    payload,
    operation_name,
    monkeypatch,
):
    def failing_operation(**kwargs):
        raise RuntimeError("Simulated agent failure")

    monkeypatch.setattr(
        service,
        operation_name,
        failing_operation,
    )

    response = TestClient(service.app).post(
        endpoint,
        json=payload,
    )

    assert response.status_code == 502
    assert "could not produce" in response.json()["detail"]
