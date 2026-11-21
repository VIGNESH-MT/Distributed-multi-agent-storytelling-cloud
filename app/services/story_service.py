
from typing import Any
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.models import Story, StoryEvent


class StoryNotFoundError(Exception):
    """Raised when the requested story does not exist."""


class StoryVersionConflictError(Exception):
    """Raised when the stored story version differs from the expected version."""


def commit_story_revision(
    session: Session,
    *,
    story_id: UUID,
    expected_version: int,
    new_content: str,
    agent_id: str,
    event_payload: dict[str, Any],
) -> int:
    """
    Atomically update a story and record its corresponding event.

    The caller owns the transaction and must commit or roll it back.

    Returns:
        The newly committed story version.

    Raises:
        StoryNotFoundError: If the requested story does not exist.
        StoryVersionConflictError: If the expected version is stale.
    """

    statement = (
        update(Story)
        .where(
            Story.id == story_id,
            Story.version == expected_version,
        )
        .values(
            content=new_content,
            version=Story.version + 1,
        )
        .returning(Story.version)
    )

    result = session.execute(statement).scalar_one_or_none()

    if result is None:
        exists = session.get(Story, story_id)

        if exists is None:
            raise StoryNotFoundError(
                f"Story {story_id} does not exist."
            )

        raise StoryVersionConflictError(
            f"Expected version {expected_version}, "
            f"but the story is currently at version {exists.version}."
        )

    event = StoryEvent(
        story_id=story_id,
        version=result,
        agent_id=agent_id,
        event_type="revision_committed",
        payload=event_payload,
    )

    session.add(event)

    # Persist the event INSERT within the current transaction.
    # Required because SessionLocal is configured with autoflush=False.
    # This does not commit the transaction.
    session.flush()

    return result
