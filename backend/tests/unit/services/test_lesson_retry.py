import uuid
from io import BytesIO

import pytest
import pytest_asyncio
from starlette.datastructures import UploadFile

from src.config import settings
from src.core.exceptions import (
    AudioFileMissingError,
    LessonNotFoundError,
    TranscriptionInProgressError,
)
from src.models.enums import UserRole
from src.models.enums.transcripts import TranscriptionModel, TranscriptStatus
from src.services.lesson import LessonService
from src.tasks.transcribe_lesson import transcribe_lesson_task

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Аудио пишется во временную папку, задача Celery не уходит в брокер."""
    monkeypatch.setattr(settings, "LESSON_AUDIO_DIR", str(tmp_path))
    queued: list[str] = []
    monkeypatch.setattr(transcribe_lesson_task, "delay", queued.append)
    return queued


@pytest_asyncio.fixture
async def teacher_id(store):
    user = await store.user.add(
        return_model=True,
        email=f"t-{uuid.uuid4()}@example.com",
        roles=[UserRole.SPECIALIST.value],
    )
    return user.id


@pytest_asyncio.fixture
async def lesson(store, teacher_id, isolated):
    """Урок со своим файлом; задача постановки при создании сбрасывается из очереди."""
    service = LessonService(store=store)
    created = await service.create_lesson(
        teacher_id=teacher_id,
        title="Урок",
        file=UploadFile(file=BytesIO(b"audio"), filename="a.mp3"),
        model=TranscriptionModel.QUALITY,
    )
    isolated.clear()
    return created


async def _transcript(store, lesson_id):
    return await store.lesson_transcript.find_one_or_none(lesson_id=lesson_id)


async def _set_status(store, lesson_id, status, **fields):
    transcript = await _transcript(store, lesson_id)
    await store.lesson_transcript.update(
        model_id=transcript.id, return_model=False, status=status, **fields
    )
    return transcript.id


async def test_failed_transcript_is_reset_and_requeued(
    store, teacher_id, lesson, isolated
):
    transcript_id = await _set_status(
        store, lesson.id, TranscriptStatus.FAILED, error="сбой"
    )

    result = await LessonService(store=store).retry_transcription(teacher_id, lesson.id)

    assert result.transcript_status == TranscriptStatus.PENDING
    transcript = await _transcript(store, lesson.id)
    assert transcript.status == TranscriptStatus.PENDING
    assert transcript.error is None
    assert isolated == [str(transcript_id)]


async def test_done_transcript_is_cleared_for_recalculation(
    store, teacher_id, lesson, isolated
):
    await _set_status(
        store,
        lesson.id,
        TranscriptStatus.DONE,
        language="ru",
        segments=[{"start": 0, "end": 1, "text": "старый текст", "speaker": None}],
        note="старое предупреждение",
    )

    await LessonService(store=store).retry_transcription(teacher_id, lesson.id)

    transcript = await _transcript(store, lesson.id)
    assert transcript.status == TranscriptStatus.PENDING
    assert transcript.segments is None
    assert transcript.language is None
    assert transcript.note is None
    assert len(isolated) == 1


async def test_retry_can_switch_the_variant(store, teacher_id, lesson):
    await _set_status(store, lesson.id, TranscriptStatus.FAILED, error="сбой")

    result = await LessonService(store=store).retry_transcription(
        teacher_id, lesson.id, model=TranscriptionModel.FAST
    )

    assert result.transcription_model == TranscriptionModel.FAST
    stored = await store.lesson.find_by_id(model_id=lesson.id)
    assert stored.transcription_model == TranscriptionModel.FAST


async def test_retry_without_model_keeps_the_variant(store, teacher_id, lesson):
    await _set_status(store, lesson.id, TranscriptStatus.FAILED, error="сбой")

    result = await LessonService(store=store).retry_transcription(teacher_id, lesson.id)

    assert result.transcription_model == TranscriptionModel.QUALITY


async def test_retry_is_refused_while_processing(store, teacher_id, lesson, isolated):
    await _set_status(store, lesson.id, TranscriptStatus.PROCESSING)

    with pytest.raises(TranscriptionInProgressError):
        await LessonService(store=store).retry_transcription(teacher_id, lesson.id)

    assert isolated == []
    assert (await _transcript(store, lesson.id)).status == TranscriptStatus.PROCESSING


async def test_retry_is_refused_when_audio_file_is_gone(
    store, teacher_id, lesson, isolated
):
    stored = await store.lesson.find_by_id(model_id=lesson.id)
    from pathlib import Path

    Path(stored.audio_path).unlink()
    await _set_status(store, lesson.id, TranscriptStatus.FAILED, error="сбой")

    with pytest.raises(AudioFileMissingError):
        await LessonService(store=store).retry_transcription(teacher_id, lesson.id)

    assert isolated == []
    # Прежняя ошибка не затёрта: запуск не состоялся.
    transcript = await _transcript(store, lesson.id)
    assert transcript.status == TranscriptStatus.FAILED
    assert transcript.error == "сбой"


async def test_other_users_lesson_cannot_be_retried(store, lesson, isolated):
    with pytest.raises(LessonNotFoundError):
        await LessonService(store=store).retry_transcription(999_999, lesson.id)

    assert isolated == []
