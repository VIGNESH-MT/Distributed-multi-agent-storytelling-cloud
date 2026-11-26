from app.agents.mock_story_agents import mock_character_agent
from app.agents.schemas import PlotProposal


def test_character_agent_creates_new_continuation_without_copying_context():
    current_story = (
        "Mira is investigating a mysterious signal. "
        "Her colleague Elias discovered an encrypted logbook."
    )
    user_request = "Continue Mira and Elias's investigation."

    plot = PlotProposal(
        central_conflict=(
            "Mira must determine why the signal "
            "is connected to Elias's logbook."
        ),
        proposed_events=[
            "Mira examines the encrypted logbook.",
            "Elias explains how he discovered the signal.",
        ],
        causal_logic=(
            "The logbook provides evidence that "
            "connects the signal to Elias."
        ),
    )

    result = mock_character_agent(
        story_title="The Mystery of the Signal",
        current_story=current_story,
        user_request=user_request,
        plot=plot,
        revision_feedback=[],
    )

    continuation = result.proposed_story_continuation

    assert "Mira examines the encrypted logbook." in continuation
    assert "Elias explains how he discovered the signal." in continuation
    assert current_story not in continuation
    assert user_request not in continuation
    assert "The central conflict remains:" not in continuation
    assert "The causal connection is:" not in continuation


def test_character_agent_uses_revision_feedback_as_guidance():
    plot = PlotProposal(
        central_conflict="Mira must investigate the signal.",
        proposed_events=[
            "Mira examines the signal.",
            "Elias checks the recorded evidence.",
        ],
        causal_logic="The evidence helps explain the signal.",
    )

    feedback = [
        "Clarify why Elias trusts the evidence.",
        "Preserve continuity with Mira's investigation.",
    ]

    result = mock_character_agent(
        story_title="The Mystery of the Signal",
        current_story="Mira is investigating a mysterious signal.",
        user_request="Continue the investigation.",
        plot=plot,
        revision_feedback=feedback,
    )

    continuation = result.proposed_story_continuation

    assert "Mira examines the signal." in continuation
    assert "Elias checks the recorded evidence." in continuation
    assert "Clarify why Elias trusts the evidence." not in continuation
    assert "Preserve continuity with Mira's investigation." not in continuation
    assert "reconsidered the evidence carefully" in continuation