"""Model-backed and mock implementations of the storytelling agents."""

import logging
import os

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.model import get_chat_model
from app.agents.mock_story_agents import (
    mock_character_agent,
    mock_critic_agent,
    mock_plot_agent,
)
from app.agents.schemas import (
    CharacterProposal,
    CriticEvaluation,
    PlotProposal,
)

logger = logging.getLogger(__name__)

AGENT_PROVIDER = os.getenv(
    "STORY_AGENT_PROVIDER",
    "gemini",
).strip().lower()

if AGENT_PROVIDER not in {"gemini", "mock"}:
    raise ValueError(
        "STORY_AGENT_PROVIDER must be either 'gemini' or 'mock'."
    )

logger.info("STORY_AGENT_PROVIDER=%s", AGENT_PROVIDER)


def _structured_model(schema):
    """Return a Gemini model configured for validated structured output."""
    return get_chat_model().with_structured_output(schema)


def run_plot_agent(
    story_title: str,
    current_story: str,
    user_request: str,
) -> PlotProposal:
    """Analyse the story and propose causal plot developments."""

    if AGENT_PROVIDER == "mock":
        return mock_plot_agent(
            story_title,
            current_story,
            user_request,
        )

    model = _structured_model(PlotProposal)

    messages = [
        SystemMessage(
            content=(
                "You are the Plot Agent in a collaborative storytelling system. "
                "Develop a coherent plot progression. Analyse the existing story "
                "rather than ignoring it. Preserve established facts, identify "
                "causal relationships, and propose meaningful developments. "
                "Do not write the entire story."
            )
        ),
        HumanMessage(
            content=(
                f"Story title: {story_title}\n\n"
                f"Current canonical story:\n{current_story}\n\n"
                f"User requirements:\n{user_request}\n\n"
                "Produce a structured plot proposal."
            )
        ),
    ]

    return model.invoke(messages)


def run_character_agent(
    story_title: str,
    current_story: str,
    user_request: str,
    plot: PlotProposal,
    revision_feedback: list[str] | None = None,
) -> CharacterProposal:
    """Develop character motivations, actions and dialogue."""

    if AGENT_PROVIDER == "mock":
        return mock_character_agent(
            story_title,
            current_story,
            user_request,
            plot,
            revision_feedback,
        )

    model = _structured_model(CharacterProposal)

    feedback = revision_feedback or ["No previous revision feedback."]

    messages = [
        SystemMessage(
            content=(
                "You are the Character and Dialogue Agent. Independently analyse "
                "the existing story and plot proposal. Develop believable "
                "motivations, character decisions and dialogue. Preserve character "
                "continuity. Integrate the plot without blindly accepting "
                "contradictory developments. Return a proposed continuation."
            )
        ),
        HumanMessage(
            content=(
                f"Story title: {story_title}\n\n"
                f"Current canonical story:\n{current_story}\n\n"
                f"User requirements:\n{user_request}\n\n"
                f"Plot proposal:\n{plot.model_dump_json(indent=2)}\n\n"
                f"Critic feedback:\n{feedback}\n\n"
                "Produce a structured character and dialogue proposal."
            )
        ),
    ]

    return model.invoke(messages)


def run_critic_agent(
    story_title: str,
    current_story: str,
    user_request: str,
    plot: PlotProposal,
    character: CharacterProposal,
) -> CriticEvaluation:
    """Evaluate narrative continuity, causality and proposal quality."""

    if AGENT_PROVIDER == "mock":
        return mock_critic_agent(
            story_title,
            current_story,
            user_request,
            plot,
            character,
        )

    model = _structured_model(CriticEvaluation)

    messages = [
        SystemMessage(
            content=(
                "You are the independent Critic and Narrative Consistency Agent. "
                "Evaluate the plot and character proposals against the canonical "
                "story and user requirements. Identify contradictions, unsupported "
                "events, broken causal links and inconsistent motivations. "
                "Be rigorous and specific. Approve only when the continuation is "
                "coherent enough to commit. A score alone does not determine "
                "approval: explain any blocking issues."
            )
        ),
        HumanMessage(
            content=(
                f"Story title: {story_title}\n\n"
                f"Canonical story:\n{current_story}\n\n"
                f"User requirements:\n{user_request}\n\n"
                f"Plot proposal:\n{plot.model_dump_json(indent=2)}\n\n"
                f"Character proposal:\n{character.model_dump_json(indent=2)}\n\n"
                "Return a structured critical evaluation."
            )
        ),
    ]

    return model.invoke(messages)
