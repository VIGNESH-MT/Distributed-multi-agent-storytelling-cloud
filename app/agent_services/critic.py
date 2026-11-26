"""Independent Critic and Narrative Consistency Agent HTTP service."""

import logging

from fastapi import HTTPException
from pydantic import BaseModel

from app.agent_services.common import (
    AgentExecutionResponse,
    create_agent_app,
    execute_remote_agent,
)
from app.agents.schemas import (
    CharacterProposal,
    CriticEvaluation,
    PlotProposal,
)
from app.agents.story_agents import run_critic_agent

logger = logging.getLogger(__name__)
app = create_agent_app("storytelling-critic-agent")


class CriticRequest(BaseModel):
    story_title: str
    current_story: str
    user_request: str
    plot: PlotProposal
    character: CharacterProposal


@app.post(
    "/evaluate",
    response_model=AgentExecutionResponse[CriticEvaluation],
)
def evaluate_proposal(
    request: CriticRequest,
) -> AgentExecutionResponse[CriticEvaluation]:
    try:
        return execute_remote_agent(
            agent="critic",
            operation=lambda: run_critic_agent(
                story_title=request.story_title,
                current_story=request.current_story,
                user_request=request.user_request,
                plot=request.plot,
                character=request.character,
            ),
        )
    except Exception as exc:
        logger.exception("Critic Agent evaluation failed")
        raise HTTPException(
            status_code=502,
            detail="Critic Agent could not produce a valid evaluation.",
        ) from exc
