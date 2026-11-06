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
    authed_psy, isolated_uploads, tmp_path
):
    resp = _upload(authed_psy)

    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Урок 1"
    assert body["transcript_status"] == "PENDING"
    assert len(isolated_uploads) == 1
    saved = list(Path(tmp_path).iterdir())
    assert len(saved) == 1
    assert saved[0].read_bytes() == b"fake-audio"


def test_upload_saves_topic(authed_psy):
    body = _upload(authed_psy, topic="  унитарное и федеративное  ").json()

    assert body["topic"] == "унитарное и федеративное"
    assert authed_psy.get(f"/lessons/{body['id']}").json()["topic"] == (
        "унитарное и федеративное"
    )


def test_upload_without_topic_leaves_it_empty(authed_psy):
    assert _upload(authed_psy).json()["topic"] is None
    assert _upload(authed_psy, topic="   ").json()["topic"] is None


def test_model_options_are_listed(authed_psy):
    resp = authed_psy.get("/lessons/models")

    assert resp.status_code == 200
    options = resp.json()
    assert [o["id"] for o in options] == ["fast", "quality"]
    assert all(o["title"] and o["description"] for o in options)


@pytest.mark.parametrize("chosen", ["fast", "quality"])
def test_upload_uses_chosen_model(authed_psy, chosen):
    body = _upload(authed_psy, model=chosen).json()

    assert body["transcription_model"] == chosen
    assert authed_psy.get(f"/lessons/{body['id']}").json()["transcription_model"] == (
        chosen
    )


def test_upload_without_model_uses_configured_default(authed_psy, monkeypatch):
    assert _upload(authed_psy).json()["transcription_model"] == "fast"

    monkeypatch.setattr(settings, "DEFAULT_TRANSCRIPTION_MODEL", "quality")

    assert _upload(authed_psy).json()["transcription_model"] == "quality"


def test_upload_rejects_unknown_model(authed_psy, isolated_uploads, tmp_path):
    resp = _upload(authed_psy, model="huge")

    assert resp.status_code == 422
    assert isolated_uploads == []
    assert list(Path(tmp_path).iterdir()) == []


def test_upload_rejects_unsupported_format(authed_psy, isolated_uploads, tmp_path):
    resp = _upload(authed_psy, name="notes.pdf")

    assert resp.status_code == 415
    assert isolated_uploads == []
    assert list(Path(tmp_path).iterdir()) == []


def test_upload_rejects_empty_file(authed_psy, isolated_uploads, tmp_path):
    resp = _upload(authed_psy, content=b"")

    assert resp.status_code == 422
    assert isolated_uploads == []
    assert list(Path(tmp_path).iterdir()) == []


def test_upload_rejects_too_large_file(
    authed_psy, isolated_uploads, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "MAX_LESSON_UPLOAD_MB", 0)

    resp = _upload(authed_psy)

    assert resp.status_code == 413
    assert isolated_uploads == []
    assert list(Path(tmp_path).iterdir()) == []


def test_get_lesson_returns_status(authed_psy):
    lesson_id = _upload(authed_psy).json()["id"]

    resp = authed_psy.get(f"/lessons/{lesson_id}")

    assert resp.status_code == 200
    assert resp.json()["transcript_status"] == "PENDING"


def test_get_transcript_before_processing_has_no_segments(authed_psy):
    lesson_id = _upload(authed_psy).json()["id"]

    resp = authed_psy.get(f"/lessons/{lesson_id}/transcript")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["segments"] == []


def test_unknown_lesson_returns_404(authed_psy):
    assert authed_psy.get(f"/lessons/{uuid.uuid4()}").status_code == 404


def test_other_users_lesson_is_hidden(authed_psy, psy_id):
    lesson_id = _upload(authed_psy).json()["id"]

    # Дальше запросы идут от имени другого пользователя; override снимает authed_psy.
    app.dependency_overrides[get_any_user_id] = lambda: psy_id + 1000

    assert authed_psy.get(f"/lessons/{lesson_id}").status_code == 404
    assert authed_psy.get(f"/lessons/{lesson_id}/transcript").status_code == 404
