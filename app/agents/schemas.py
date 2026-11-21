from pydantic import BaseModel, Field, field_validator


class PlotProposal(BaseModel):
    central_conflict: str = Field(min_length=10)
    proposed_events: list[str] = Field(min_length=2, max_length=5)
    causal_logic: str = Field(min_length=10)
    unresolved_questions: list[str] = Field(default_factory=list)

    @field_validator("proposed_events")
    @classmethod
    def validate_events(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("Proposed events cannot be empty.")
        return values


class CharacterProposal(BaseModel):
    character_developments: list[str] = Field(min_length=1, max_length=5)
    dialogue: list[str] = Field(min_length=1, max_length=5)
    motivations: list[str] = Field(min_length=1, max_length=5)
    proposed_story_continuation: str = Field(min_length=20)

    @field_validator(
        "character_developments",
        "dialogue",
        "motivations",
    )
    @classmethod
    def validate_nonempty_entries(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("List entries cannot be empty.")
        return values


class CriticEvaluation(BaseModel):
    approved: bool
    coherence_score: int = Field(ge=0, le=100)
    continuity_issues: list[str] = Field(default_factory=list)
    causal_issues: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=10)
