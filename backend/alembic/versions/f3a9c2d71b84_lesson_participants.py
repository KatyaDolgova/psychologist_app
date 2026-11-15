"""lesson_participants

С кем автор поделился уроком (решение AI-04, docs/TRANSCRIPTION.md, раздел 11).

Revision ID: f3a9c2d71b84
Revises: d8e2f1a9c3b6
Create Date: 2026-11-15 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a9c2d71b84"
down_revision: Union[str, Sequence[str], None] = "d8e2f1a9c3b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "lesson_participants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lesson_id", "user_id", name="uq_lesson_participant"),
    )
    op.create_index(
        op.f("ix_lesson_participants_lesson_id"),
        "lesson_participants",
        ["lesson_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lesson_participants_user_id"),
        "lesson_participants",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_lesson_participants_user_id"), table_name="lesson_participants"
    )
    op.drop_index(
        op.f("ix_lesson_participants_lesson_id"), table_name="lesson_participants"
    )
    op.drop_table("lesson_participants")
