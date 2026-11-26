from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from pydantic import ValidationError

from app.agents.provenance import AgentExecutionTrace
from app.agents.graph import run_story_workflow
from app.db.models import Story
from app.services.story_service import (
    StoryNotFoundError,
    StoryVersionConflictError,
    commit_story_revision,
)


def execute_agentic_revision(
    session: Session,
    *,
    story_id: UUID,
    expected_version: int,
    user_request: str,
) -> dict[str, Any]:
    """Generate, evaluate and conditionally commit an agentic revision.

    Database transactions are deliberately separated from model inference.
    The final commit uses optimistic version checking to reject stale work.
    """

    if not user_request.strip():
        raise ValueError("User request cannot be empty.")

    # Phase 1: Read an immutable snapshot.
    story = session.get(Story, story_id)

    if story is None:
        session.rollback()
        raise StoryNotFoundError(f"Story {story_id} does not exist.")

    snapshot = {
        "id": story.id,
        "title": story.title,
        "content": story.content,
        "version": story.version,
    }

    session.rollback()

    if snapshot["version"] != expected_version:
        raise StoryVersionConflictError(
            f"Expected version {expected_version}, "
            f"but the story is currently at version "
            f"{snapshot['version']}."
        )

    # Phase 2: Run model inference outside a database transaction.
    result = run_story_workflow(
        story_title=snapshot["title"],
        current_story=snapshot["content"],
        user_request=user_request,
    )

    critic = result["critic_evaluation"]

    # Validate execution evidence independently at the persistence boundary.
    expected_agents = ["plot"] + (
        ["character", "critic"] * result["critic_evaluations"]
    )

    try:
        validated_traces = [
            AgentExecutionTrace.model_validate(trace)
            for trace in result.get("agent_traces", [])
        ]
        observed_agents = [
            trace.agent for trace in validated_traces
        ]
        trace_complete = (
            result.get("trace_coverage") == "complete"
            and observed_agents == expected_agents
            and result["revision_attempts"]
            == result["critic_evaluations"] - 1
        )
    except (ValidationError, TypeError, ValueError):
        validated_traces = []
        trace_complete = False

    provenance = {
        "workflow": "langgraph_proposal_critique_revision",
        "base_version": expected_version,
        "critic_evaluations": result["critic_evaluations"],
        "revision_attempts": result["revision_attempts"],
        "trace_coverage": (
            "complete" if trace_complete else "incomplete"
        ),
        "agent_traces": [
            trace.model_dump(mode="json")
            for trace in validated_traces
        ],
        "critic_evaluation": critic.model_dump(mode="json"),
        "plot_proposal": result["plot_proposal"].model_dump(mode="json"),
        "character_proposal": result["character_proposal"].model_dump(
            mode="json"
        ),
    }

    if result["workflow_status"] == "approved" and not trace_complete:
        raise ValueError(
            "Approved revision cannot be committed because "
            "execution provenance is incomplete."
        )

    if result["workflow_status"] != "approved":
        return {
            "story_id": story_id,
            "status": "rejected",
            "base_version": expected_version,
            "committed_version": None,
            "critic_score": critic.coherence_score,
            "critic_evaluations": result["critic_evaluations"],
            "revision_attempts": result["revision_attempts"],
            "provenance": provenance,
        }

    # Phase 3: Commit using compare-and-swap version protection.
    continuation = (
        result["character_proposal"].proposed_story_continuation.strip()
    )

    if not continuation:
        raise ValueError("The approved story continuation is empty.")

    new_content = (
        f'{snapshot["content"].rstrip()}\n\n{continuation}'
        if snapshot["content"].strip()
        else continuation
    )

    with session.begin():
        committed_version = commit_story_revision(
            session,
            story_id=story_id,
            expected_version=expected_version,
            new_content=new_content,
            agent_id="langgraph-coordinator",
            event_payload=provenance,
        )

    return {
        "story_id": story_id,
        "status": "committed",
        "base_version": expected_version,
        "committed_version": committed_version,
        "critic_score": critic.coherence_score,
        "critic_evaluations": result["critic_evaluations"],
        "revision_attempts": result["revision_attempts"],
        "provenance": provenance,
    }


