from src.crud.impl.base import BaseDAO
from src.models.lesson_transcript import LessonTranscript


class LessonTranscriptDAO(BaseDAO):
    """DAO для транскриптов уроков."""

    model = LessonTranscript
