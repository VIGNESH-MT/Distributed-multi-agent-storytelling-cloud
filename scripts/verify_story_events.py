
from uuid import UUID

from sqlalchemy import select

from app.db.models import StoryEvent
from app.db.session import SessionLocal


STORY_ID = "38f23a67-6335-4a64-b11e-9247e7a64ebe"


def main():
    story_id = UUID(STORY_ID)

    with SessionLocal() as db:
        events = db.scalars(
            select(StoryEvent)
            .where(StoryEvent.story_id == story_id)
            .order_by(StoryEvent.version)
        ).all()

        for event in events:
            print("Version:", event.version)
            print("Agent:", event.agent_id)
            print("Event type:", event.event_type)
            print("Payload:", event.payload)
            print("---")

        print("Total committed events:", len(events))


if __name__ == "__main__":
    main()
