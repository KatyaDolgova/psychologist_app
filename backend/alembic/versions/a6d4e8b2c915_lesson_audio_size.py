"""lesson audio size

Размер загруженного файла для суточного лимита загрузки (AI-14). У старых уроков
размер неизвестен и остаётся пустым: в лимит они не входят.

Revision ID: a6d4e8b2c915
Revises: f3a9c2d71b84
Create Date: 2026-11-15 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a6d4e8b2c915"
down_revision: Union[str, Sequence[str], None] = "f3a9c2d71b84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "lessons", sa.Column("audio_size_bytes", sa.BigInteger(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("lessons", "audio_size_bytes")
