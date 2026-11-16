"""Суточный лимит загрузки записей (AI-14)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from main import app
from src.config import settings
from src.core.dependencies import get_any_user_id
from src.tasks.transcribe_lesson import transcribe_lesson_task

MB = 1024 * 1024


@pytest.fixture(autouse=True)
def small_daily_limit(tmp_path, monkeypatch):
    """Лимит 2 МБ в сутки, аудио во временной папке, Celery подменён."""
    monkeypatch.setattr(settings, "LESSON_AUDIO_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "LESSON_DAILY_UPLOAD_MB", 2)
    monkeypatch.setattr(transcribe_lesson_task, "delay", lambda *_: None)


def _upload(client, size_mb: float):
    return client.post(
        "/lessons/",
        data={"title": "Урок"},
        files={"file": ("lesson.mp3", b"x" * int(size_mb * MB), "audio/mpeg")},
    )


def test_uploads_up_to_the_limit_are_accepted(authed_specialist):
    assert _upload(authed_specialist, 1).status_code == 201
    # Ровно на границе лимита загрузка ещё проходит.
    assert _upload(authed_specialist, 1).status_code == 201


def test_upload_over_the_limit_is_rejected_and_not_kept(authed_specialist, tmp_path):
    assert _upload(authed_specialist, 1).status_code == 201

    resp = _upload(authed_specialist, 1.5)

    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert "2 МБ" in detail
    assert "освобождаться через" in detail
    assert len(list(tmp_path.iterdir())) == 1
    assert len(authed_specialist.get("/lessons/").json()) == 1


def test_rejected_upload_does_not_use_up_the_limit(authed_specialist):
    _upload(authed_specialist, 1)
    assert _upload(authed_specialist, 1.5).status_code == 429

    assert _upload(authed_specialist, 0.5).status_code == 201


def test_exhausted_limit_rejects_any_upload(authed_specialist):
    _upload(authed_specialist, 1)
    _upload(authed_specialist, 1)

    assert _upload(authed_specialist, 0.01).status_code == 429


def test_per_file_limit_still_applies(authed_specialist, monkeypatch):
    monkeypatch.setattr(settings, "MAX_LESSON_UPLOAD_MB", 1)

    assert _upload(authed_specialist, 1.5).status_code == 413


@pytest.mark.asyncio
async def test_uploads_older_than_a_day_do_not_count(authed_specialist, store):
    ids = [_upload(authed_specialist, 1).json()["id"] for _ in range(2)]
    assert _upload(authed_specialist, 1).status_code == 429

    day_ago = datetime.now(timezone.utc) - timedelta(hours=25)
    for lesson_id in ids:
        await store.lesson.update(
            model_id=uuid.UUID(lesson_id), return_model=False, created_at=day_ago
        )
    await store.session.commit()

    assert _upload(authed_specialist, 1).status_code == 201


def test_retry_is_not_counted(authed_specialist):
    lesson_id = _upload(authed_specialist, 1).json()["id"]
    _upload(authed_specialist, 1)

    assert authed_specialist.post(f"/lessons/{lesson_id}/retry").status_code == 200


def test_limit_is_per_user(authed_specialist, client_id):
    _upload(authed_specialist, 1)
    _upload(authed_specialist, 1)

    app.dependency_overrides[get_any_user_id] = lambda: client_id

    assert _upload(authed_specialist, 1).status_code == 201
