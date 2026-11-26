"""Independent Character and Dialogue Agent HTTP service."""

import logging

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.agent_services.common import (
    AgentExecutionResponse,
    create_agent_app,
    execute_remote_agent,
)
from app.agents.schemas import CharacterProposal, PlotProposal
from app.agents.story_agents import run_character_agent

logger = logging.getLogger(__name__)
app = create_agent_app("storytelling-character-agent")


class CharacterRequest(BaseModel):
    story_title: str
    current_story: str
    user_request: str
    plot: PlotProposal
    revision_feedback: list[str] = Field(default_factory=list)


@app.post(
    "/propose",
    response_model=AgentExecutionResponse[CharacterProposal],
)
def propose_characters(
    request: CharacterRequest,
) -> AgentExecutionResponse[CharacterProposal]:
    try:
        return execute_remote_agent(
            agent="character",
            operation=lambda: run_character_agent(
                story_title=request.story_title,
                current_story=request.current_story,
                user_request=request.user_request,
                plot=request.plot,
                revision_feedback=request.revision_feedback,
            ),
        )
    except Exception as exc:
        logger.exception("Character Agent inference failed")
        raise HTTPException(
            status_code=502,
            detail="Character Agent could not produce a valid proposal.",
        ) from exc
