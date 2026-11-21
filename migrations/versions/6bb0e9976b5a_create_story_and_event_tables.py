"""create story and event tables

Revision ID: 6bb0e9976b5a
Revises:
Create Date: 2026-11-21 20:31:44.423079

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '6bb0e9976b5a'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the application story tables."""

    op.create_table(
        'stories',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'story_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('story_id', sa.UUID(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.String(length=100), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column(
            'payload',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['story_id'],
            ['stories.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(
        'ix_story_events_story_created',
        'story_events',
        ['story_id', 'created_at'],
        unique=False,
    )

    op.create_index(
        'ix_story_events_story_version',
        'story_events',
        ['story_id', 'version'],
        unique=False,
    )


def downgrade() -> None:
    """Remove the application story tables."""

    op.drop_index(
        'ix_story_events_story_version',
        table_name='story_events',
    )
    op.drop_index(
        'ix_story_events_story_created',
        table_name='story_events',
    )
    op.drop_table('story_events')
    op.drop_table('stories')
