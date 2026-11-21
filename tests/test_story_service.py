from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import Story, StoryEvent
from app.db.session import SessionLocal
from app.services.story_service import (
    StoryNotFoundError,
    StoryVersionConflictError,
    commit_story_revision,
)


def test_successful_commit_and_stale_version_rejection():
    session = SessionLocal()
    transaction = session.begin()

    try:
        story = Story(
            title="Consistency integration test",
            content="Initial story.",
            version=1,
        )
        session.add(story)
        session.flush()

        story_id = story.id

        committed_version = commit_story_revision(
            session,
            story_id=story_id,
            expected_version=1,
            new_content="First accepted revision.",
            agent_id="plot-agent-test",
            event_payload={"action": "initial_revision"},
        )

        assert committed_version == 2

        updated_story = session.get(Story, story_id)
        assert updated_story.version == 2
        assert updated_story.content == "First accepted revision."

        events = session.scalars(
            select(StoryEvent).where(
                StoryEvent.story_id == story_id
            )
        ).all()

        assert len(events) == 1
        assert events[0].version == 2
        assert events[0].agent_id == "plot-agent-test"

        with pytest.raises(StoryVersionConflictError):
            commit_story_revision(
                session,
                story_id=story_id,
                expected_version=1,
                new_content="Stale competing revision.",
                agent_id="dialogue-agent-test",
                event_payload={"action": "stale_revision"},
            )

        # The rejected proposal must not alter the accepted story.
        session.refresh(updated_story)
        assert updated_story.version == 2
        assert updated_story.content == "First accepted revision."

        events_after_conflict = session.scalars(
            select(StoryEvent).where(
                StoryEvent.story_id == story_id
            )
        ).all()

        assert len(events_after_conflict) == 1

    finally:
        transaction.rollback()
        session.close()


def test_missing_story_is_rejected():
    session = SessionLocal()
    transaction = session.begin()

    try:
        with pytest.raises(StoryNotFoundError):
            commit_story_revision(
                session,
                story_id=uuid4(),
                expected_version=1,
                new_content="This story does not exist.",
                agent_id="plot-agent-test",
                event_payload={"action": "missing_story_test"},
            )
    finally:
        transaction.rollback()
        session.close()
