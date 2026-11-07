"""rename psychologist to specialist

Написана вручную: autogenerate не видит переименований и сгенерировал бы
удаление таблиц вместе с данными.

Revision ID: d8e2f1a9c3b6
Revises: b7c1d2e3f4a5
Create Date: 2026-11-07 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8e2f1a9c3b6"
down_revision: Union[str, Sequence[str], None] = "b7c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_ROLE = "PSYCHOLOGIST"
NEW_ROLE = "SPECIALIST"

# userrole не используется ни одной колонкой, но на него опирается
# downgrade миграции fb76ec6ae4e7, поэтому значение меняется и в нём.
ROLE_ENUMS = ("appointmentrole", "userrole")

TABLES = (
    ("psychologist_profiles", "specialist_profiles"),
    ("psychologist_working_hours", "specialist_working_hours"),
    ("psychologist_availability_slots", "specialist_availability_slots"),
)

# Таблицы указаны под старыми именами, колонка psychologist_id становится specialist_id.
COLUMN_TABLES = (
    "psychologist_working_hours",
    "psychologist_availability_slots",
    "client_notes",
    "user_favorites",
)

# (таблица под новым именем, старое имя ограничения, новое имя ограничения)
CONSTRAINTS = (
    (
        "specialist_profiles",
        "psychologist_profiles_pkey",
        "specialist_profiles_pkey",
    ),
    (
        "specialist_profiles",
        "psychologist_profiles_id_fkey",
        "specialist_profiles_id_fkey",
    ),
    (
        "specialist_working_hours",
        "psychologist_working_hours_pkey",
        "specialist_working_hours_pkey",
    ),
    (
        "specialist_working_hours",
        "psychologist_working_hours_psychologist_id_fkey",
        "specialist_working_hours_specialist_id_fkey",
    ),
    (
        "specialist_availability_slots",
        "psychologist_availability_slots_pkey",
        "specialist_availability_slots_pkey",
    ),
    (
        "specialist_availability_slots",
        "psychologist_availability_slots_psychologist_id_fkey",
        "specialist_availability_slots_specialist_id_fkey",
    ),
    (
        "specialist_availability_slots",
        "uq_slot_psy_starts",
        "uq_slot_specialist_starts",
    ),
    (
        "client_notes",
        "client_notes_psychologist_id_fkey",
        "client_notes_specialist_id_fkey",
    ),
    (
        "user_favorites",
        "user_favorites_psychologist_id_fkey",
        "user_favorites_specialist_id_fkey",
    ),
    (
        "user_favorites",
        "uq_favorites_user_psychologist",
        "uq_favorites_user_specialist",
    ),
)

INDEXES = (
    ("ix_slots_psy_status_starts", "ix_slots_specialist_status_starts"),
    ("ix_client_notes_psychologist_id", "ix_client_notes_specialist_id"),
)

SEQUENCES = (("psychologist_working_hours_id_seq", "specialist_working_hours_id_seq"),)


def _rename_roles(old: str, new: str) -> None:
    for enum_name in ROLE_ENUMS:
        op.execute(f"ALTER TYPE {enum_name} RENAME VALUE '{old}' TO '{new}'")
    op.execute(
        f"""
        UPDATE users
           SET roles = replace(roles::text, '"{old}"', '"{new}"')::jsonb
         WHERE roles @> '["{old}"]'::jsonb
        """
    )


def upgrade() -> None:
    """Upgrade schema."""
    for table in COLUMN_TABLES:
        op.alter_column(table, "psychologist_id", new_column_name="specialist_id")
    for old, new in TABLES:
        op.rename_table(old, new)
    for table, old, new in CONSTRAINTS:
        op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new}")
    for old, new in INDEXES:
        op.execute(f"ALTER INDEX {old} RENAME TO {new}")
    for old, new in SEQUENCES:
        op.execute(f"ALTER SEQUENCE {old} RENAME TO {new}")
    _rename_roles(OLD_ROLE, NEW_ROLE)


def downgrade() -> None:
    """Downgrade schema."""
    _rename_roles(NEW_ROLE, OLD_ROLE)
    for old, new in SEQUENCES:
        op.execute(f"ALTER SEQUENCE {new} RENAME TO {old}")
    for old, new in INDEXES:
        op.execute(f"ALTER INDEX {new} RENAME TO {old}")
    for table, old, new in CONSTRAINTS:
        op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {new} TO {old}")
    for old, new in TABLES:
        op.rename_table(new, old)
    for table in COLUMN_TABLES:
        op.alter_column(table, "specialist_id", new_column_name="psychologist_id")
