import uuid
from typing import Optional

from sqlalchemy import JSON, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseWithTimestamps
from src.models.enums.transcripts import TranscriptStatus


class LessonTranscript(BaseWithTimestamps):
    """Транскрипт записи урока (один урок - один транскрипт).

    segments - список {"start", "end", "text", "speaker"}, общий формат для любых
    источников аудио.
    """

    __tablename__ = "lesson_transcripts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), unique=True, index=True
    )
    status: Mapped[TranscriptStatus] = mapped_column(
        Enum(TranscriptStatus), default=TranscriptStatus.PENDING
    )
    language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    segments: Mapped[Optional[list]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
