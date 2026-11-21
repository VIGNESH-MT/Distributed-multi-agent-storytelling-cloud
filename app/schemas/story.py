from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StoryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    initial_content: str = ""


class StoryRevisionRequest(BaseModel):
    expected_version: int = Field(ge=1)
    new_content: str
    agent_id: str = Field(min_length=1, max_length=100)
    event_payload: dict[str, Any] = Field(default_factory=dict)


class AgenticRevisionRequest(BaseModel):
    expected_version: int = Field(ge=1)
    user_request: str = Field(min_length=10, max_length=4000)


class StoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    content: str
    version: int
    created_at: datetime
    updated_at: datetime


class StoryRevisionResponse(BaseModel):
    story_id: UUID
    committed_version: int
    status: str


class AgenticRevisionResponse(BaseModel):
    story_id: UUID
    status: str
    base_version: int
    committed_version: int | None
    critic_score: int
    critic_evaluations: int
    revision_attempts: int
    provenance: dict[str, Any]
