from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Story
from app.db.session import SessionLocal

from app.schemas.story import (
    AgenticRevisionRequest,
    AgenticRevisionResponse,
    StoryCreate,
    StoryResponse,
    StoryRevisionRequest,
    StoryRevisionResponse,
)

from app.services.story_service import (
    StoryNotFoundError,
    StoryVersionConflictError,
    commit_story_revision,
)

from app.services.agent_workflow_service import (
    execute_agentic_revision,
)


router = APIRouter(prefix="/stories", tags=["stories"])


def get_db():
    """Provide one database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post(
    "",
    response_model=StoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_story(
    request: StoryCreate,
    db: Session = Depends(get_db),
):
    """Create a new story at version 1."""
    story = Story(
        title=request.title,
        content=request.initial_content,
        version=1,
    )

    with db.begin():
        db.add(story)
        db.flush()
        db.refresh(story)

    return story


@router.get(
    "/{story_id}",
    response_model=StoryResponse,
)
def get_story(
    story_id: UUID,
    db: Session = Depends(get_db),
):
    """Retrieve the latest committed story."""
    story = db.get(Story, story_id)

    if story is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found.",
        )

    return story


@router.post(
    "/{story_id}/revisions",
    response_model=StoryRevisionResponse,
)
def revise_story(
    story_id: UUID,
    request: StoryRevisionRequest,
    db: Session = Depends(get_db),
):
    """Commit a manual revision with version protection."""
    try:
        with db.begin():
            committed_version = commit_story_revision(
                db,
                story_id=story_id,
                expected_version=request.expected_version,
                new_content=request.new_content,
                agent_id=request.agent_id,
                event_payload=request.event_payload,
            )

    except StoryVersionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except StoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return StoryRevisionResponse(
        story_id=story_id,
        committed_version=committed_version,
        status="committed",
    )


@router.post(
    "/{story_id}/agentic-revisions",
    response_model=AgenticRevisionResponse,
)
def create_agentic_revision(
    story_id: UUID,
    request: AgenticRevisionRequest,
    db: Session = Depends(get_db),
):
    """Generate, critique and conditionally commit an agentic revision."""

    try:
        result = execute_agentic_revision(
            db,
            story_id=story_id,
            expected_version=request.expected_version,
            user_request=request.user_request,
        )

    except StoryVersionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except StoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return AgenticRevisionResponse(**result)
