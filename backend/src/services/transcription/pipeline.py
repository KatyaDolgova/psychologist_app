from dataclasses import dataclass
from uuid import UUID

from src.crud import Store
from src.models.enums.transcripts import TranscriptionModel, TranscriptStatus
from src.services.transcription.base import TranscriptionResult

ERROR_MAX_LENGTH = 1000


@dataclass(frozen=True)
class ProcessingJob:
    """Что нужно воркеру для распознавания."""

    audio_path: str
    prompt: str | None
    model: TranscriptionModel


async def start_processing(store: Store, transcript_id: UUID) -> ProcessingJob | None:
    """Переводит транскрипт в PROCESSING и возвращает аудио, подсказку и вариант модели.

    Подсказка — тема урока, а если она не указана, его название.
    Возвращает None, если транскрипт не найден, уже обработан или без аудио —
    задача тогда ничего не делает (повторный запуск Celery безопасен).
    """
    transcript = await store.lesson_transcript.find_by_id(model_id=transcript_id)
    if transcript is None or transcript.status in (
        TranscriptStatus.PROCESSING,
        TranscriptStatus.DONE,
    ):
        return None
    lesson = await store.lesson.find_by_id(model_id=transcript.lesson_id)
    if lesson is None or not lesson.audio_path:
        await save_failure(store, transcript_id, "У урока нет аудиофайла")
        return None
    await store.lesson_transcript.update(
        model_id=transcript_id,
        return_model=False,
        status=TranscriptStatus.PROCESSING,
        error=None,
    )
    return ProcessingJob(
        audio_path=lesson.audio_path,
        prompt=lesson.topic or lesson.title,
        model=lesson.transcription_model,
    )


async def save_result(
    store: Store,
    transcript_id: UUID,
    result: TranscriptionResult,
    note: str | None = None,
) -> None:
    await store.lesson_transcript.update(
        model_id=transcript_id,
        return_model=False,
        status=TranscriptStatus.DONE,
        language=result.language,
        segments=[segment.to_dict() for segment in result.segments],
        error=None,
        note=note,
    )


async def save_failure(store: Store, transcript_id: UUID, error: str) -> None:
    await store.lesson_transcript.update(
        model_id=transcript_id,
        return_model=False,
        status=TranscriptStatus.FAILED,
        error=error[:ERROR_MAX_LENGTH],
    )
