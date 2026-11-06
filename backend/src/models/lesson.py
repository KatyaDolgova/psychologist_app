import uuid
from typing import Optional

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseWithTimestamps
from src.models.enums.transcripts import TranscriptionModel


class Lesson(BaseWithTimestamps):
    """Урок: запись, которую специалист загрузил для транскрибации и разбора.

    Минимальная сущность нового формата: пока только автор, название и аудио.
    Дальше к ней привязываются транскрипт и материалы (конспект, вопросы-ответы).
    """

    __tablename__ = "lessons"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    # Тема или ключевые слова: подсказка распознаванию, чтобы верно писать термины.
    topic: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Вариант транскрибации, выбранный пользователем (fast / quality).
    transcription_model: Mapped[TranscriptionModel] = mapped_column(
        Enum(TranscriptionModel), default=TranscriptionModel.FAST
    )
    audio_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
