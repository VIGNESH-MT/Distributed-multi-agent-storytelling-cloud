from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.schemas import (
    CharacterProposal,
    CriticEvaluation,
    PlotProposal,
)
from app.agents.story_agents import (
    run_character_agent,
    run_critic_agent,
    run_plot_agent,
)


MAX_REVISION_ATTEMPTS = 2


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


def plot_node(state: StoryWorkflowState) -> dict:
    proposal = run_plot_agent(
        story_title=state["story_title"],
        current_story=state["current_story"],
        user_request=state["user_request"],
    )

    return {
        "plot_proposal": proposal,
        "workflow_status": "plot_proposed",
    }


def character_node(state: StoryWorkflowState) -> dict:
    proposal = run_character_agent(
        story_title=state["story_title"],
        current_story=state["current_story"],
        user_request=state["user_request"],
        plot=state["plot_proposal"],
        revision_feedback=state["revision_feedback"],
    )

    return {
        "character_proposal": proposal,
        "workflow_status": "character_proposed",
    }


def critic_node(state: StoryWorkflowState) -> dict:
    evaluation = run_critic_agent(
        story_title=state["story_title"],
        current_story=state["current_story"],
        user_request=state["user_request"],
        plot=state["plot_proposal"],
        character=state["character_proposal"],
    )

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
        "workflow_status": status,
    }


def route_after_critic(
    state: StoryWorkflowState,
) -> Literal["revise", "finish"]:
    if state["workflow_status"] == "revision_required":
        return "revise"

    return "finish"


def build_story_graph():
    """Build a bounded proposal, critique and revision workflow."""

    builder = StateGraph(StoryWorkflowState)

    builder.add_node("plot", plot_node)
    builder.add_node("character", character_node)
    builder.add_node("critic", critic_node)

    builder.add_edge(START, "plot")
    builder.add_edge("plot", "character")
    builder.add_edge("character", "critic")

    builder.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "revise": "character",
            "finish": END,
        },
    )

    return builder.compile()


story_graph = build_story_graph()


def run_story_workflow(
    *,
    story_title: str,
    current_story: str,
    user_request: str,
) -> StoryWorkflowState:
    """Run the multi-agent workflow for one storytelling request."""

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
    }

    return story_graph.invoke(initial_state)
