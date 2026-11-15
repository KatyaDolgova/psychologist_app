import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseWithTimestamps


class LessonParticipant(BaseWithTimestamps):
    """Пользователь, с которым автор поделился уроком.

    Участник видит урок и текст, но не аудио, ошибки и повтор. Правила доступа:
    docs/TRANSCRIPTION.md, раздел 11.
    """

    __tablename__ = "lesson_participants"
    __table_args__ = (
        UniqueConstraint("lesson_id", "user_id", name="uq_lesson_participant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
