"""HTTP clients used by the LangGraph coordinator to call remote agents."""

import os

import httpx

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


def _post_agent(
    *,
    base_url: str,
    endpoint: str,
    payload: dict,
) -> dict:
    """Call one agent service with bounded connection and response timeouts."""

    timeout = httpx.Timeout(240.0, connect=5.0)

    try:
        with httpx.Client(timeout=timeout) as client:
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


def call_plot_agent(
    *,
    story_title: str,
    current_story: str,
    user_request: str,
) -> PlotProposal:
    result = _post_agent(
        base_url=PLOT_AGENT_URL,
        endpoint="/propose",
        payload={
            "story_title": story_title,
            "current_story": current_story,
            "user_request": user_request,
        },
    )
    return PlotProposal.model_validate(result)


def call_character_agent(
    *,
    story_title: str,
    current_story: str,
    user_request: str,
    plot: PlotProposal,
    revision_feedback: list[str] | None = None,
) -> CharacterProposal:
    result = _post_agent(
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
    return CharacterProposal.model_validate(result)


def call_critic_agent(
    *,
    story_title: str,
    current_story: str,
    user_request: str,
    plot: PlotProposal,
    character: CharacterProposal,
) -> CriticEvaluation:
    result = _post_agent(
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
    return CriticEvaluation.model_validate(result)
