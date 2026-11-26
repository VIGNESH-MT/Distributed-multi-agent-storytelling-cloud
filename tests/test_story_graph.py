import pytest
from pydantic import ValidationError

import app.agents.graph as graph_module

from app.agents.schemas import (
    CharacterProposal,
    CriticEvaluation,
    PlotProposal,
)


def make_plot():
    return PlotProposal(
        central_conflict="Mira must investigate a mysterious signal.",
        proposed_events=[
            "Mira decodes the signal.",
            "Mira discovers Elias's hidden logbook.",
        ],
        causal_logic="The decoded signal reveals a connection to Elias.",
    )


def make_character():
    return CharacterProposal(
        character_developments=[
            "Mira becomes more independent."
        ],
        dialogue=[
            'Mira whispered, "What are you hiding, Elias?"'
        ],
        motivations=[
            "Mira wants to understand the mysterious signal."
        ],
        proposed_story_continuation=(
            "Mira discovered the old logbook and confronted Elias."
        ),
    )


def make_critic(approved):
    return CriticEvaluation(
        approved=approved,
        coherence_score=90 if approved else 45,
        continuity_issues=[] if approved else [
            "The character motivation needs clarification."
        ],
        causal_issues=[] if approved else [
            "The discovery needs a stronger causal explanation."
        ],
        revision_instructions=[] if approved else [
            "Clarify why Mira decides to investigate."
        ],
        explanation=(
            "The proposal is coherent and consistent."
            if approved
            else "The proposal requires further revision."
        ),
    )


def initial_state():
    return {
        "story_title": "Test Story",
        "current_story": "Mira discovers a mysterious signal.",
        "user_request": "Continue the story coherently.",
        "plot_proposal": None,
        "character_proposal": None,
        "critic_evaluation": None,
        "revision_feedback": [],
        "revision_attempts": 0,
        "critic_evaluations": 0,
        "workflow_status": "started",
        "agent_traces": [],
        "trace_coverage": "pending",
    }


def test_character_dialogue_is_required():
    with pytest.raises(ValidationError):
        CharacterProposal(
            character_developments=["Mira becomes independent."],
            dialogue=[],
            motivations=["Mira seeks the truth."],
            proposed_story_continuation=(
                "Mira decides to investigate the signal."
            ),
        )


def test_approved_workflow_requires_one_critic_evaluation(monkeypatch):
    monkeypatch.setattr(
        graph_module,
        "run_plot_agent",
        lambda **kwargs: make_plot(),
    )

    monkeypatch.setattr(
        graph_module,
        "run_character_agent",
        lambda **kwargs: make_character(),
    )

    monkeypatch.setattr(
        graph_module,
        "run_critic_agent",
        lambda **kwargs: make_critic(True),
    )

    result = graph_module.build_story_graph().invoke(initial_state())

    assert result["workflow_status"] == "approved"
    assert result["critic_evaluations"] == 1
    assert result["revision_attempts"] == 0


def test_revision_limit_is_enforced(monkeypatch):
    monkeypatch.setattr(
        graph_module,
        "run_plot_agent",
        lambda **kwargs: make_plot(),
    )

    monkeypatch.setattr(
        graph_module,
        "run_character_agent",
        lambda **kwargs: make_character(),
    )

    monkeypatch.setattr(
        graph_module,
        "run_critic_agent",
        lambda **kwargs: make_critic(False),
    )

    result = graph_module.build_story_graph().invoke(initial_state())

    assert result["workflow_status"] == "rejected"
    assert result["revision_attempts"] == 2
    assert result["critic_evaluations"] == 3


def test_revision_feedback_reaches_character_agent(monkeypatch):
    feedback_received = []

    monkeypatch.setattr(
        graph_module,
        "run_plot_agent",
        lambda **kwargs: make_plot(),
    )

    def character_agent(**kwargs):
        feedback_received.append(kwargs["revision_feedback"])
        return make_character()

    monkeypatch.setattr(
        graph_module,
        "run_character_agent",
        character_agent,
    )

    critic_results = iter([
        make_critic(False),
        make_critic(True),
    ])

    monkeypatch.setattr(
        graph_module,
        "run_critic_agent",
        lambda **kwargs: next(critic_results),
    )

    result = graph_module.build_story_graph().invoke(initial_state())

    assert result["workflow_status"] == "approved"
    assert result["revision_attempts"] == 1
    assert result["critic_evaluations"] == 2
    assert len(feedback_received) == 2
    assert feedback_received[1] == [
        "Clarify why Mira decides to investigate."
    ]

def test_approved_workflow_records_three_agent_traces(monkeypatch):
    monkeypatch.setattr(graph_module, "AGENT_PROVIDER", "mock")

    monkeypatch.setattr(
        graph_module,
        "run_plot_agent",
        lambda **kwargs: make_plot(),
    )
    monkeypatch.setattr(
        graph_module,
        "run_character_agent",
        lambda **kwargs: make_character(),
    )
    monkeypatch.setattr(
        graph_module,
        "run_critic_agent",
        lambda **kwargs: make_critic(True),
    )

    result = graph_module.build_story_graph().invoke(initial_state())

    traces = result["agent_traces"]

    assert result["workflow_status"] == "approved"
    assert len(traces) == 3
    assert [trace["agent"] for trace in traces] == [
        "plot", "character", "critic"
    ]

    for trace in traces:
        assert trace["provider"] == "mock"
        assert trace["model"] is None
        assert trace["execution_location"] == "local"
        assert trace["duration_ms"] >= 0

    assert result["trace_coverage"] == "complete"


def test_revision_workflow_records_every_execution(monkeypatch):
    monkeypatch.setattr(graph_module, "AGENT_PROVIDER", "mock")

    monkeypatch.setattr(
        graph_module,
        "run_plot_agent",
        lambda **kwargs: make_plot(),
    )
    monkeypatch.setattr(
        graph_module,
        "run_character_agent",
        lambda **kwargs: make_character(),
    )

    critic_results = iter([
        make_critic(False),
        make_critic(True),
    ])

    monkeypatch.setattr(
        graph_module,
        "run_critic_agent",
        lambda **kwargs: next(critic_results),
    )

    result = graph_module.build_story_graph().invoke(initial_state())

    traces = result["agent_traces"]

    assert result["workflow_status"] == "approved"
    assert result["revision_attempts"] == 1
    assert len(traces) == 5

    assert [trace["agent"] for trace in traces] == [
        "plot", "character", "critic", "character", "critic"
    ]


def test_rejected_workflow_records_all_execution_attempts(monkeypatch):
    monkeypatch.setattr(graph_module, "AGENT_PROVIDER", "mock")

    monkeypatch.setattr(
        graph_module,
        "run_plot_agent",
        lambda **kwargs: make_plot(),
    )
    monkeypatch.setattr(
        graph_module,
        "run_character_agent",
        lambda **kwargs: make_character(),
    )
    monkeypatch.setattr(
        graph_module,
        "run_critic_agent",
        lambda **kwargs: make_critic(False),
    )

    result = graph_module.build_story_graph().invoke(initial_state())

    traces = result["agent_traces"]

    assert result["workflow_status"] == "rejected"
    assert result["revision_attempts"] == 2
    assert result["critic_evaluations"] == 3
    assert len(traces) == 7

    assert [trace["agent"] for trace in traces] == [
        "plot",
        "character", "critic",
        "character", "critic",
        "character", "critic",
    ]



from app.agents.provenance import AgentExecutionTrace


def make_remote_trace(agent):
    return AgentExecutionTrace(
        agent=agent,
        provider="mock",
        model=None,
        execution_location="remote",
        duration_ms=12.5,
    )


def test_remote_approved_workflow_records_three_agent_traces(monkeypatch):
    import app.agents.remote_agents as remote_agents

    monkeypatch.setattr(graph_module, "AGENT_EXECUTION_MODE", "remote")

    monkeypatch.setattr(
        remote_agents,
        "call_plot_agent",
        lambda **kwargs: (make_plot(), make_remote_trace("plot")),
    )
    monkeypatch.setattr(
        remote_agents,
        "call_character_agent",
        lambda **kwargs: (
            make_character(),
            make_remote_trace("character"),
        ),
    )
    monkeypatch.setattr(
        remote_agents,
        "call_critic_agent",
        lambda **kwargs: (
            make_critic(True),
            make_remote_trace("critic"),
        ),
    )

    result = graph_module.run_story_workflow(
        story_title="Test Story",
        current_story="Mira discovers a mysterious signal.",
        user_request="Continue the story coherently.",
    )

    traces = result["agent_traces"]

    assert result["workflow_status"] == "approved"
    assert len(traces) == 3
    assert [trace["agent"] for trace in traces] == [
        "plot", "character", "critic"
    ]

    for trace in traces:
        assert trace["provider"] == "mock"
        assert trace["execution_location"] == "remote"
        assert trace["duration_ms"] >= 0

    assert result["trace_coverage"] == "complete"


def test_remote_revision_workflow_records_every_execution(monkeypatch):
    import app.agents.remote_agents as remote_agents

    monkeypatch.setattr(graph_module, "AGENT_EXECUTION_MODE", "remote")

    monkeypatch.setattr(
        remote_agents,
        "call_plot_agent",
        lambda **kwargs: (make_plot(), make_remote_trace("plot")),
    )
    monkeypatch.setattr(
        remote_agents,
        "call_character_agent",
        lambda **kwargs: (
            make_character(),
            make_remote_trace("character"),
        ),
    )

    critic_results = iter([
        make_critic(False),
        make_critic(True),
    ])

    monkeypatch.setattr(
        remote_agents,
        "call_critic_agent",
        lambda **kwargs: (
            next(critic_results),
            make_remote_trace("critic"),
        ),
    )

    result = graph_module.run_story_workflow(
        story_title="Test Story",
        current_story="Mira discovers a mysterious signal.",
        user_request="Continue the story coherently.",
    )

    traces = result["agent_traces"]

    assert result["workflow_status"] == "approved"
    assert result["revision_attempts"] == 1
    assert len(traces) == 5

    assert [trace["agent"] for trace in traces] == [
        "plot", "character", "critic", "character", "critic"
    ]

    assert all(
        trace["execution_location"] == "remote"
        for trace in traces
    )


def test_remote_rejected_workflow_records_all_execution_attempts(
    monkeypatch,
):
    import app.agents.remote_agents as remote_agents

    monkeypatch.setattr(graph_module, "AGENT_EXECUTION_MODE", "remote")

    monkeypatch.setattr(
        remote_agents,
        "call_plot_agent",
        lambda **kwargs: (make_plot(), make_remote_trace("plot")),
    )
    monkeypatch.setattr(
        remote_agents,
        "call_character_agent",
        lambda **kwargs: (
            make_character(),
            make_remote_trace("character"),
        ),
    )
    monkeypatch.setattr(
        remote_agents,
        "call_critic_agent",
        lambda **kwargs: (
            make_critic(False),
            make_remote_trace("critic"),
        ),
    )

    result = graph_module.run_story_workflow(
        story_title="Test Story",
        current_story="Mira discovers a mysterious signal.",
        user_request="Continue the story coherently.",
    )

    traces = result["agent_traces"]

    assert result["workflow_status"] == "rejected"
    assert result["revision_attempts"] == 2
    assert result["critic_evaluations"] == 3
    assert len(traces) == 7

    assert [trace["agent"] for trace in traces] == [
        "plot",
        "character", "critic",
        "character", "critic",
        "character", "critic",
    ]

    assert all(
        trace["execution_location"] == "remote"
        for trace in traces
    )


def test_trace_coverage_accepts_complete_execution_sequence():
    state = {
        "critic_evaluations": 1,
        "agent_traces": [
            make_remote_trace("plot").model_dump(mode="json"),
            make_remote_trace("character").model_dump(mode="json"),
            make_remote_trace("critic").model_dump(mode="json"),
        ],
    }

    assert graph_module.finalize_trace_coverage(state) == {
        "trace_coverage": "complete"
    }


def test_trace_coverage_rejects_missing_execution():
    state = {
        "critic_evaluations": 1,
        "agent_traces": [
            make_remote_trace("plot").model_dump(mode="json"),
            make_remote_trace("character").model_dump(mode="json"),
        ],
    }

    assert graph_module.finalize_trace_coverage(state) == {
        "trace_coverage": "incomplete"
    }


def test_trace_coverage_rejects_duplicate_execution():
    state = {
        "critic_evaluations": 1,
        "agent_traces": [
            make_remote_trace("plot").model_dump(mode="json"),
            make_remote_trace("character").model_dump(mode="json"),
            make_remote_trace("character").model_dump(mode="json"),
        ],
    }

    assert graph_module.finalize_trace_coverage(state) == {
        "trace_coverage": "incomplete"
    }


def test_trace_coverage_rejects_invalid_provider_metadata():
    invalid_trace = make_remote_trace("plot").model_dump(mode="json")
    invalid_trace["provider"] = "unrecognised-provider"

    state = {
        "critic_evaluations": 1,
        "agent_traces": [
            invalid_trace,
            make_remote_trace("character").model_dump(mode="json"),
            make_remote_trace("critic").model_dump(mode="json"),
        ],
    }

    assert graph_module.finalize_trace_coverage(state) == {
        "trace_coverage": "incomplete"
    }
