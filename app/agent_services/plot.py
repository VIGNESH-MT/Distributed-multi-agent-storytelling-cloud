"""Independent Plot Agent HTTP service."""

import logging

from fastapi import HTTPException
from pydantic import BaseModel

from app.agent_services.common import (
    AgentExecutionResponse,
    create_agent_app,
    execute_remote_agent,
)
from app.agents.schemas import PlotProposal
from app.agents.story_agents import run_plot_agent

logger = logging.getLogger(__name__)
app = create_agent_app("storytelling-plot-agent")


class PlotRequest(BaseModel):
    story_title: str
    current_story: str
    user_request: str


@app.post(
    "/propose",
    response_model=AgentExecutionResponse[PlotProposal],
)
def propose_plot(
    request: PlotRequest,
) -> AgentExecutionResponse[PlotProposal]:
    try:
        return execute_remote_agent(
            agent="plot",
            operation=lambda: run_plot_agent(
                story_title=request.story_title,
                current_story=request.current_story,
                user_request=request.user_request,
            ),
        )
    except Exception as exc:
        logger.exception("Plot Agent inference failed")
        raise HTTPException(
            status_code=502,
            detail="Plot Agent could not produce a valid proposal.",
        ) from exc

