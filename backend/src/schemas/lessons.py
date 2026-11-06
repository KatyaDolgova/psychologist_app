from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from src.models.enums.transcripts import TranscriptionModel, TranscriptStatus


class ModelOptionSchema(BaseModel):
    id: TranscriptionModel
    title: str
    description: str


class LessonSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    topic: str | None = None
    transcription_model: TranscriptionModel
    created_at: datetime
    transcript_status: TranscriptStatus | None = None


class SegmentSchema(BaseModel):
    start: float
    end: float
    text: str
    speaker: str | None = None


class TranscriptSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lesson_id: UUID
    status: TranscriptStatus
    language: str | None = None
    segments: list[SegmentSchema] = []
    error: str | None = None
    updated_at: datetime

    @field_validator("segments", mode="before")
    @classmethod
    def _no_segments_yet(cls, value):
        # До окончания распознавания в БД лежит NULL.
        return value or []
