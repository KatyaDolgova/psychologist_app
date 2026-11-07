import uuid
from pathlib import Path

import pytest

from main import app
from src.config import settings
from src.core.dependencies import get_any_user_id
from src.tasks.transcribe_lesson import transcribe_lesson_task


@pytest.fixture(autouse=True)
def isolated_uploads(tmp_path, monkeypatch):
    """Аудио пишется во временную папку, задача Celery не уходит в брокер."""
    monkeypatch.setattr(settings, "LESSON_AUDIO_DIR", str(tmp_path))
    queued: list[str] = []
    monkeypatch.setattr(transcribe_lesson_task, "delay", queued.append)
    return queued


def _upload(client, name="lesson.mp3", content=b"fake-audio", title="Урок 1", **extra):
    return client.post(
        "/lessons/",
        data={"title": title, **extra},
        files={"file": (name, content, "audio/mpeg")},
    )


def test_upload_creates_lesson_and_queues_transcription(
    authed_specialist, isolated_uploads, tmp_path
):
    resp = _upload(authed_specialist)

    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Урок 1"
    assert body["transcript_status"] == "PENDING"
    assert len(isolated_uploads) == 1
    saved = list(Path(tmp_path).iterdir())
    assert len(saved) == 1
    assert saved[0].read_bytes() == b"fake-audio"


def test_upload_saves_topic(authed_specialist):
    body = _upload(authed_specialist, topic="  унитарное и федеративное  ").json()

    assert body["topic"] == "унитарное и федеративное"
    assert authed_specialist.get(f"/lessons/{body['id']}").json()["topic"] == (
        "унитарное и федеративное"
    )


def test_upload_without_topic_leaves_it_empty(authed_specialist):
    assert _upload(authed_specialist).json()["topic"] is None
    assert _upload(authed_specialist, topic="   ").json()["topic"] is None


def test_model_options_are_listed(authed_specialist):
    resp = authed_specialist.get("/lessons/models")

    assert resp.status_code == 200
    options = resp.json()
    assert [o["id"] for o in options] == ["fast", "quality"]
    assert all(o["title"] and o["description"] for o in options)


@pytest.mark.parametrize("chosen", ["fast", "quality"])
def test_upload_uses_chosen_model(authed_specialist, chosen):
    body = _upload(authed_specialist, model=chosen).json()

    assert body["transcription_model"] == chosen
    assert authed_specialist.get(f"/lessons/{body['id']}").json()[
        "transcription_model"
    ] == (chosen)


def test_upload_without_model_uses_configured_default(authed_specialist, monkeypatch):
    assert _upload(authed_specialist).json()["transcription_model"] == "fast"

    monkeypatch.setattr(settings, "DEFAULT_TRANSCRIPTION_MODEL", "quality")

    assert _upload(authed_specialist).json()["transcription_model"] == "quality"


def test_upload_rejects_unknown_model(authed_specialist, isolated_uploads, tmp_path):
    resp = _upload(authed_specialist, model="huge")

    assert resp.status_code == 422
    assert isolated_uploads == []
    assert list(Path(tmp_path).iterdir()) == []


def test_upload_rejects_unsupported_format(
    authed_specialist, isolated_uploads, tmp_path
):
    resp = _upload(authed_specialist, name="notes.pdf")

    assert resp.status_code == 415
    assert isolated_uploads == []
    assert list(Path(tmp_path).iterdir()) == []


def test_upload_rejects_empty_file(authed_specialist, isolated_uploads, tmp_path):
    resp = _upload(authed_specialist, content=b"")

    assert resp.status_code == 422
    assert isolated_uploads == []
    assert list(Path(tmp_path).iterdir()) == []


def test_upload_rejects_too_large_file(
    authed_specialist, isolated_uploads, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "MAX_LESSON_UPLOAD_MB", 0)

    resp = _upload(authed_specialist)

    assert resp.status_code == 413
    assert isolated_uploads == []
    assert list(Path(tmp_path).iterdir()) == []


def test_get_lesson_returns_status(authed_specialist):
    lesson_id = _upload(authed_specialist).json()["id"]

    resp = authed_specialist.get(f"/lessons/{lesson_id}")

    assert resp.status_code == 200
    assert resp.json()["transcript_status"] == "PENDING"


def test_get_transcript_before_processing_has_no_segments(authed_specialist):
    lesson_id = _upload(authed_specialist).json()["id"]

    resp = authed_specialist.get(f"/lessons/{lesson_id}/transcript")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["segments"] == []


def test_unknown_lesson_returns_404(authed_specialist):
    assert authed_specialist.get(f"/lessons/{uuid.uuid4()}").status_code == 404


def test_other_users_lesson_is_hidden(authed_specialist, specialist_id):
    lesson_id = _upload(authed_specialist).json()["id"]

    # Дальше запросы идут от имени другого пользователя; override снимает authed_specialist.
    app.dependency_overrides[get_any_user_id] = lambda: specialist_id + 1000

    assert authed_specialist.get(f"/lessons/{lesson_id}").status_code == 404
    assert authed_specialist.get(f"/lessons/{lesson_id}/transcript").status_code == 404


def test_retry_requeues_the_transcription(authed_specialist, isolated_uploads):
    lesson_id = _upload(authed_specialist).json()["id"]
    assert len(isolated_uploads) == 1

    resp = authed_specialist.post(f"/lessons/{lesson_id}/retry")

    assert resp.status_code == 200
    assert resp.json()["transcript_status"] == "PENDING"
    assert len(isolated_uploads) == 2


def test_retry_can_choose_another_variant(authed_specialist):
    lesson_id = _upload(authed_specialist, model="fast").json()["id"]

    resp = authed_specialist.post(
        f"/lessons/{lesson_id}/retry", json={"model": "quality"}
    )

    assert resp.status_code == 200
    assert resp.json()["transcription_model"] == "quality"
    got = authed_specialist.get(f"/lessons/{lesson_id}").json()
    assert got["transcription_model"] == "quality"


def test_retry_rejects_unknown_variant(authed_specialist, isolated_uploads):
    lesson_id = _upload(authed_specialist).json()["id"]

    resp = authed_specialist.post(f"/lessons/{lesson_id}/retry", json={"model": "huge"})

    assert resp.status_code == 422
    assert len(isolated_uploads) == 1


def test_retry_of_unknown_lesson_returns_404(authed_specialist):
    assert authed_specialist.post(f"/lessons/{uuid.uuid4()}/retry").status_code == 404


def test_retry_of_other_users_lesson_returns_404(authed_specialist, specialist_id):
    lesson_id = _upload(authed_specialist).json()["id"]
    app.dependency_overrides[get_any_user_id] = lambda: specialist_id + 1000

    assert authed_specialist.post(f"/lessons/{lesson_id}/retry").status_code == 404
