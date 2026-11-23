"""Deterministic mock agents for infrastructure and integration testing.

These functions do not call an LLM and must not be used to measure
semantic narrative quality.
"""

import logging

from app.agents.schemas import (
    CharacterProposal,
    CriticEvaluation,
    PlotProposal,
)

logger = logging.getLogger(__name__)


def mock_plot_agent(
    story_title: str,
    current_story: str,
    user_request: str,
) -> PlotProposal:
    logger.warning(
        "MOCK_PROVIDER=mock: deterministic Plot Agent fixture; no LLM call."
    )

    return PlotProposal(
        central_conflict=(
            "The investigators must determine whether the unexplained "
            "anomaly is a trustworthy warning or a mechanism that could "
            "mislead their decisions."
        ),
        proposed_events=[
            (
                "The lead investigator verifies the anomaly against an "
                "independent reference instrument and records the baseline."
            ),
            (
                "The systems engineer isolates the affected subsystem; "
                "a second observation reproduces the anomaly."
            ),
            (
                "The team defines a controlled observation linked to the "
                "predicted event and records the result independently."
            ),
        ],
        causal_logic=(
            "Independent verification first rules out a simple display "
            "error. Reproduction under isolation establishes that the "
            "anomaly is not limited to the original instrument. A controlled "
            "observation then tests the prediction without changing the "
            "evidence being collected."
        ),
        unresolved_questions=[
            "What is the origin of the anomaly?",
            "Can its predicted event be independently verified?",
        ],
    )


def mock_character_agent(
    story_title: str,
    current_story: str,
    user_request: str,
    plot: PlotProposal,
    revision_feedback: list[str] | None = None,
) -> CharacterProposal:
    logger.warning(
        "MOCK_PROVIDER=mock: deterministic Character Agent fixture; "
        "no LLM call."
    )

    return CharacterProposal(
        character_developments=[
            (
                "The lead investigator becomes more methodical and insists "
                "on independent verification before accepting an explanation."
            ),
            (
                "The systems engineer moves from immediate fault correction "
                "towards preserving evidence and testing competing explanations."
            ),
        ],
        dialogue=[
            (
                'Investigator: "We need independent evidence before '
                'we decide what this means."'
            ),
            (
                'Engineer: "I will isolate the subsystem and record '
                'each observation."'
            ),
        ],
        motivations=[
            "The investigator wants a reliable explanation supported by evidence.",
            "The engineer wants to identify the anomaly without destroying evidence.",
        ],
        proposed_story_continuation=(
            "The investigator and engineer agree to preserve the original "
            "measurements while conducting an independent observation. "
            "They document their predictions in advance and separate the "
            "test equipment from the affected subsystem. This approach "
            "allows them to compare the eventual observation with the "
            "recorded prediction without relying on the original instrument."
        ),
    )


def mock_critic_agent(
    story_title: str,
    current_story: str,
    user_request: str,
    plot: PlotProposal,
    character: CharacterProposal,
) -> CriticEvaluation:
    logger.warning(
        "MOCK_PROVIDER=mock: deterministic structural Critic checks; "
        "no LLM evaluation."
    )

    checks = {
        "plot_events_present": len(plot.proposed_events) >= 2,
        "causal_logic_present": bool(plot.causal_logic.strip()),
        "character_continuation_present": (
            len(character.proposed_story_continuation.strip()) >= 20
        ),
        "dialogue_present": bool(character.dialogue),
        "motivations_present": bool(character.motivations),
    }

    failures = [
        name for name, passed in checks.items() if not passed
    ]

    approved = len(failures) == 0

    return CriticEvaluation(
        approved=approved,
        coherence_score=70 if approved else 0,
        continuity_issues=[],
        causal_issues=[],
        revision_instructions=[
            f"Mock structural check failed: {name}"
            for name in failures
        ],
        explanation=(
            "MOCK MODE: This evaluation checks required proposal structure "
            "and field completeness only. It does not assess semantic "
            "narrative coherence or replace a model-based critic. "
            + (
                "All deterministic structural checks passed."
                if approved
                else "One or more structural checks failed."
            )
        ),
    )
