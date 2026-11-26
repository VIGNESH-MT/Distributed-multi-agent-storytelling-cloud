"""LangGraph orchestration for local or distributed storytelling agents."""

import os
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.provenance import (
    AgentExecutionTrace,
    execute_agent_with_trace,
)
from pydantic import ValidationError
from app.agents.schemas import (
    CharacterProposal,
    CriticEvaluation,
    PlotProposal,
)
from app.agents.story_agents import (
    AGENT_PROVIDER,
    run_character_agent,
    run_critic_agent,
    run_plot_agent,
)

MAX_REVISION_ATTEMPTS = 2

AGENT_EXECUTION_MODE = os.getenv(
    "AGENT_EXECUTION_MODE",
    "local",
).strip().lower()

if AGENT_EXECUTION_MODE not in {"local", "remote"}:
    raise ValueError(
        "AGENT_EXECUTION_MODE must be either 'local' or 'remote'."
    )


class StoryWorkflowState(TypedDict):
    story_title: str
    current_story: str
    user_request: str

    plot_proposal: PlotProposal | None
    character_proposal: CharacterProposal | None
    critic_evaluation: CriticEvaluation | None

    revision_feedback: list[str]
    revision_attempts: int
    critic_evaluations: int
    workflow_status: str

    agent_traces: list[dict]
    trace_coverage: Literal["pending", "complete", "incomplete"]


def plot_node(state: StoryWorkflowState) -> dict:
    traces = state.get("agent_traces", [])

    if AGENT_EXECUTION_MODE == "remote":
        from app.agents.remote_agents import call_plot_agent

        proposal, trace = call_plot_agent(
            story_title=state["story_title"],
            current_story=state["current_story"],
            user_request=state["user_request"],
        )
        traces = [*traces, trace.model_dump(mode="json")]
    else:
        proposal, trace = execute_agent_with_trace(
            agent="plot",
            provider=AGENT_PROVIDER,
            execution_location="local",
            operation=lambda: run_plot_agent(
                story_title=state["story_title"],
                current_story=state["current_story"],
                user_request=state["user_request"],
            ),
        )
        traces = [*traces, trace.model_dump(mode="json")]

    return {
        "plot_proposal": proposal,
        "agent_traces": traces,
        "workflow_status": "plot_proposed",
    }


def character_node(state: StoryWorkflowState) -> dict:
    plot = state["plot_proposal"]

    if plot is None:
        raise RuntimeError("Character Agent requires a plot proposal.")

    traces = state.get("agent_traces", [])

    if AGENT_EXECUTION_MODE == "remote":
        from app.agents.remote_agents import call_character_agent

        proposal, trace = call_character_agent(
            story_title=state["story_title"],
            current_story=state["current_story"],
            user_request=state["user_request"],
            plot=plot,
            revision_feedback=state["revision_feedback"],
        )
        traces = [*traces, trace.model_dump(mode="json")]
    else:
        proposal, trace = execute_agent_with_trace(
            agent="character",
            provider=AGENT_PROVIDER,
            execution_location="local",
            operation=lambda: run_character_agent(
                story_title=state["story_title"],
                current_story=state["current_story"],
                user_request=state["user_request"],
                plot=plot,
                revision_feedback=state["revision_feedback"],
            ),
        )
        traces = [*traces, trace.model_dump(mode="json")]

    return {
        "character_proposal": proposal,
        "agent_traces": traces,
        "workflow_status": "character_proposed",
    }


def critic_node(state: StoryWorkflowState) -> dict:
    plot = state["plot_proposal"]
    character = state["character_proposal"]

    if plot is None or character is None:
        raise RuntimeError(
            "Critic Agent requires both plot and character proposals."
        )

    traces = state.get("agent_traces", [])

    if AGENT_EXECUTION_MODE == "remote":
        from app.agents.remote_agents import call_critic_agent

        evaluation, trace = call_critic_agent(
            story_title=state["story_title"],
            current_story=state["current_story"],
            user_request=state["user_request"],
            plot=plot,
            character=character,
        )
        traces = [*traces, trace.model_dump(mode="json")]
    else:
        evaluation, trace = execute_agent_with_trace(
            agent="critic",
            provider=AGENT_PROVIDER,
            execution_location="local",
            operation=lambda: run_critic_agent(
                story_title=state["story_title"],
                current_story=state["current_story"],
                user_request=state["user_request"],
                plot=plot,
                character=character,
            ),
        )
        traces = [*traces, trace.model_dump(mode="json")]

    evaluations = state["critic_evaluations"] + 1
    revisions = state["revision_attempts"]

    if evaluation.approved:
        status = "approved"
        feedback = []

    elif revisions < MAX_REVISION_ATTEMPTS:
        status = "revision_required"
        feedback = evaluation.revision_instructions or [
            "Improve narrative coherence and address the critic's findings."
        ]
        revisions += 1

    else:
        status = "rejected"
        feedback = evaluation.revision_instructions

    return {
        "critic_evaluation": evaluation,
        "critic_evaluations": evaluations,
        "revision_attempts": revisions,
        "revision_feedback": feedback,
        "agent_traces": traces,
        "workflow_status": status,
    }


def finalize_trace_coverage(state: StoryWorkflowState) -> dict:
    """Validate that every expected agent execution has a valid trace."""

    expected_agents = ["plot"] + (
        ["character", "critic"] * state["critic_evaluations"]
    )

    try:
        validated_traces = [
            AgentExecutionTrace.model_validate(trace)
            for trace in state.get("agent_traces", [])
        ]

        observed_agents = [
            trace.agent for trace in validated_traces
        ]

        complete = observed_agents == expected_agents

    except (ValidationError, TypeError, ValueError):
        complete = False

    return {
        "trace_coverage": "complete" if complete else "incomplete"
    }


def route_after_critic(
    state: StoryWorkflowState,
) -> Literal["revise", "finish"]:
    if state["workflow_status"] == "revision_required":
        return "revise"

    return "finish"


def build_story_graph():
    """Build the bounded proposal, critique and revision workflow."""

    builder = StateGraph(StoryWorkflowState)

    builder.add_node("plot", plot_node)
    builder.add_node("character", character_node)
    builder.add_node("critic", critic_node)
    builder.add_node("finalize", finalize_trace_coverage)

    builder.add_edge(START, "plot")
    builder.add_edge("plot", "character")
    builder.add_edge("character", "critic")

    builder.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "revise": "character",
            "finish": "finalize",
        },
    )

    builder.add_edge("finalize", END)

    return builder.compile()


story_graph = build_story_graph()


def run_story_workflow(
    *,
    story_title: str,
    current_story: str,
    user_request: str,
) -> StoryWorkflowState:
    """Run one complete storytelling workflow."""

    initial_state: StoryWorkflowState = {
        "story_title": story_title,
        "current_story": current_story,
        "user_request": user_request,
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

    return story_graph.invoke(initial_state)



