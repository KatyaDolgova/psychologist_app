import uuid

import pytest
import pytest_asyncio

from src.models.enums import UserRole
from src.models.enums.transcripts import TranscriptionModel, TranscriptStatus
from src.services.transcription import pipeline
from src.services.transcription.base import Segment, TranscriptionResult

pytestmark = pytest.mark.asyncio


async def _make_transcript(
    store,
    audio_path: str | None = "/media/a.ogg",
    topic: str | None = None,
    model: TranscriptionModel = TranscriptionModel.QUALITY,
):
    user = await store.user.add(
        return_model=True,
        email=f"t-{uuid.uuid4()}@example.com",
        roles=[UserRole.SPECIALIST.value],
    )
    lesson = await store.lesson.add(
        teacher_id=user.id,
        title="Урок",
        topic=topic,
        transcription_model=model,
        audio_path=audio_path,
    )
    return await store.lesson_transcript.add(
        lesson_id=lesson.id, status=TranscriptStatus.PENDING
    )


@pytest_asyncio.fixture
async def transcript(store):
    return await _make_transcript(store)


async def test_start_processing_marks_processing_and_returns_job(store, transcript):
    job = await pipeline.start_processing(store, transcript.id)

    assert job.audio_path == "/media/a.ogg"
    refreshed = await store.lesson_transcript.find_by_id(model_id=transcript.id)
    assert refreshed.status == TranscriptStatus.PROCESSING


@pytest.mark.parametrize("model", list(TranscriptionModel))
async def test_job_carries_lessons_chosen_model(store, model):
    transcript = await _make_transcript(store, model=model)

    job = await pipeline.start_processing(store, transcript.id)

    assert job.model == model


async def test_prompt_is_lesson_topic_when_given(store):
    transcript = await _make_transcript(store, topic="унитарное и федеративное")

    job = await pipeline.start_processing(store, transcript.id)

    assert job.prompt == "унитарное и федеративное"


async def test_no_prompt_when_topic_is_not_given(store, transcript):
    # Название урока в подсказку не подставляется: см. docstring start_processing.
    job = await pipeline.start_processing(store, transcript.id)

    assert job.prompt is None


async def test_start_processing_skips_finished_transcript(store, transcript):
    await pipeline.save_result(
        store, transcript.id, TranscriptionResult(language="ru", segments=[])
    )

    assert await pipeline.start_processing(store, transcript.id) is None


async def test_start_processing_skips_already_processing(store, transcript):
    await pipeline.start_processing(store, transcript.id)

    assert await pipeline.start_processing(store, transcript.id) is None


async def test_start_processing_unknown_transcript_returns_none(store):
    assert await pipeline.start_processing(store, uuid.uuid4()) is None


async def test_start_processing_without_audio_fails_transcript(store):
    transcript = await _make_transcript(store, audio_path=None)

    assert await pipeline.start_processing(store, transcript.id) is None
    refreshed = await store.lesson_transcript.find_by_id(model_id=transcript.id)
    assert refreshed.status == TranscriptStatus.FAILED
    assert refreshed.error


async def test_save_result_stores_segments(store, transcript):
    await pipeline.save_result(
        store,
        transcript.id,
        TranscriptionResult(
            language="ru",
            segments=[Segment(0.0, 2.5, "Здравствуйте"), Segment(2.5, 5.0, "Урок")],
        ),
    )

    refreshed = await store.lesson_transcript.find_by_id(model_id=transcript.id)
    assert refreshed.status == TranscriptStatus.DONE
    assert refreshed.language == "ru"
    assert [s["text"] for s in refreshed.segments] == ["Здравствуйте", "Урок"]
    assert refreshed.segments[1]["start"] == 2.5


async def test_save_result_stores_note(store, transcript):
    await pipeline.save_result(
        store,
        transcript.id,
        TranscriptionResult(language="ru", segments=[]),
        note="использован запасной вариант",
    )

    refreshed = await store.lesson_transcript.find_by_id(model_id=transcript.id)
    assert refreshed.status == TranscriptStatus.DONE
    assert refreshed.note == "использован запасной вариант"


async def test_save_result_without_note_leaves_it_empty(store, transcript):
    await pipeline.save_result(
        store, transcript.id, TranscriptionResult(language="ru", segments=[])
    )

    refreshed = await store.lesson_transcript.find_by_id(model_id=transcript.id)
    assert refreshed.note is None


async def test_save_failure_truncates_error(store, transcript):
    await pipeline.save_failure(store, transcript.id, "x" * 5000)

    refreshed = await store.lesson_transcript.find_by_id(model_id=transcript.id)
    assert refreshed.status == TranscriptStatus.FAILED
    assert len(refreshed.error) == pipeline.ERROR_MAX_LENGTH
