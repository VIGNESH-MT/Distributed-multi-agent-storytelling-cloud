"""HTTP clients used by the LangGraph coordinator to call remote agents."""

import os

import httpx

from app.agent_services.common import AgentExecutionResponse
from app.agents.provenance import AgentExecutionTrace
from app.agents.schemas import (
    CharacterProposal,
    CriticEvaluation,
    PlotProposal,
)


PLOT_AGENT_URL = os.getenv(
    "PLOT_AGENT_URL",
    "http://storytelling-plot-agent:8000",
).rstrip("/")

CHARACTER_AGENT_URL = os.getenv(
    "CHARACTER_AGENT_URL",
    "http://storytelling-character-agent:8000",
).rstrip("/")

CRITIC_AGENT_URL = os.getenv(
    "CRITIC_AGENT_URL",
    "http://storytelling-critic-agent:8000",
).rstrip("/")

AGENT_REQUEST_TIMEOUT_SECONDS = float(
    os.getenv("AGENT_REQUEST_TIMEOUT_SECONDS", "240")
)

# Only failed connection attempts are retried (e.g. a pod being replaced
# during scaling or a rolling update); requests that reached an agent are not.
AGENT_CONNECT_RETRIES = int(os.getenv("AGENT_CONNECT_RETRIES", "2"))


def _post_agent(
    *,
    base_url: str,
    endpoint: str,
    payload: dict,
) -> dict:
    """Call one agent service with bounded connection and response timeouts."""

    timeout = httpx.Timeout(AGENT_REQUEST_TIMEOUT_SECONDS, connect=5.0)
    transport = httpx.HTTPTransport(retries=AGENT_CONNECT_RETRIES)

    try:
        with httpx.Client(timeout=timeout, transport=transport) as client:
            response = client.post(
                f"{base_url}{endpoint}",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"Agent request failed for {base_url}{endpoint}: {exc}"
        ) from exc


def _parse_agent_response(
    *,
    response: dict,
    result_type: type,
    expected_agent: str,
):
    """Validate a remote result and its execution provenance."""

    envelope = AgentExecutionResponse[result_type].model_validate(response)
    trace = envelope.trace

    if trace.agent != expected_agent:
        raise ValueError(
            f"Expected {expected_agent} trace, received {trace.agent}."
        )

    if trace.execution_location != "remote":
        raise ValueError(
            "Remote agent returned an invalid execution location."
        )

    return envelope.result, trace


def call_plot_agent(
    *,
    story_title: str,
    current_story: str,
    user_request: str,
) -> tuple[PlotProposal, AgentExecutionTrace]:
    response = _post_agent(
        base_url=PLOT_AGENT_URL,
        endpoint="/propose",
        payload={
            "story_title": story_title,
            "current_story": current_story,
            "user_request": user_request,
        },
    )

    return _parse_agent_response(
        response=response,
        result_type=PlotProposal,
        expected_agent="plot",
    )


def call_character_agent(
    *,
    story_title: str,
    current_story: str,
    user_request: str,
    plot: PlotProposal,
    revision_feedback: list[str] | None = None,
) -> tuple[CharacterProposal, AgentExecutionTrace]:
    response = _post_agent(
        base_url=CHARACTER_AGENT_URL,
        endpoint="/propose",
        payload={
            "story_title": story_title,
            "current_story": current_story,
            "user_request": user_request,
            "plot": plot.model_dump(mode="json"),
            "revision_feedback": revision_feedback or [],
        },
    )

    return _parse_agent_response(
        response=response,
        result_type=CharacterProposal,
        expected_agent="character",
    )


def call_critic_agent(
    *,
    story_title: str,
    current_story: str,
    user_request: str,
    plot: PlotProposal,
    character: CharacterProposal,
) -> tuple[CriticEvaluation, AgentExecutionTrace]:
    response = _post_agent(
        base_url=CRITIC_AGENT_URL,
        endpoint="/evaluate",
        payload={
            "story_title": story_title,
            "current_story": current_story,
            "user_request": user_request,
            "plot": plot.model_dump(mode="json"),
            "character": character.model_dump(mode="json"),
        },
    )

    return _parse_agent_response(
        response=response,
        result_type=CriticEvaluation,
        expected_agent="critic",
    )
