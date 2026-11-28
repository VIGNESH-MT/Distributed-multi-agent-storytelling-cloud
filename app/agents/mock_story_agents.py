"""Deterministic mock agents for infrastructure and integration testing.

These functions do not call an LLM and must not be used to measure
semantic narrative quality.

MOCK_AGENT_CPU_MS optionally makes each mock call consume that much CPU
time, so autoscaling and throughput experiments generate a measurable
synthetic load. Results obtained this way must be reported as synthetic.
"""

import logging
import os
import time

from app.agents.schemas import (
    CharacterProposal,
    CriticEvaluation,
    PlotProposal,
)

logger = logging.getLogger(__name__)


def _simulate_inference_cost() -> None:
    try:
        budget_ms = int(os.getenv("MOCK_AGENT_CPU_MS", "0") or 0)
    except ValueError:
        budget_ms = 0

    if budget_ms <= 0:
        return

    deadline = time.perf_counter() + budget_ms / 1000
    value = 0

    while time.perf_counter() < deadline:
        value = (value * 31 + 7) % 1_000_003


def mock_plot_agent(
    story_title: str,
    current_story: str,
    user_request: str,
) -> PlotProposal:
    logger.warning(
        "MOCK_PROVIDER=mock: deterministic Plot Agent fixture; no LLM call."
    )
    _simulate_inference_cost()

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
        "MOCK_PROVIDER=mock: deterministic context-aware Character Agent; "
        "no LLM call."
    )
    _simulate_inference_cost()

    events = [
        event.strip()
        for event in plot.proposed_events
        if event.strip()
    ]

    dialogue = (
        '"We need to examine the evidence before deciding what it means," '
        "one character said."
    )

    continuation_parts = events + [dialogue]

    if revision_feedback:
        continuation_parts.append(
            "The investigators reconsidered the evidence carefully "
            "before deciding how to proceed."
        )

    return CharacterProposal(
        character_developments=[
            "The characters respond to the unfolding events "
            "by examining the available evidence."
        ],
        dialogue=[dialogue],
        motivations=[
            f"The characters seek to resolve: {plot.central_conflict}"
        ],
        proposed_story_continuation=" ".join(continuation_parts),
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
    _simulate_inference_cost()

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
