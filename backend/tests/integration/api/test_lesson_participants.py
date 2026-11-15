"""Кто видит урок: автор и участники (docs/TRANSCRIPTION.md, раздел 11)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from main import app
from src.config import settings
from src.core.dependencies import get_any_user_id
from src.models.enums import UserRole
from src.models.enums.appointments import AppointmentRole
from src.models.enums.slots import SlotSource, SlotStatus
from src.models.enums.transcripts import TranscriptStatus
from src.tasks.transcribe_lesson import transcribe_lesson_task


@pytest.fixture(autouse=True)
def isolated_uploads(tmp_path, monkeypatch):
    """Аудио пишется во временную папку, задача Celery не уходит в брокер."""
    monkeypatch.setattr(settings, "LESSON_AUDIO_DIR", str(tmp_path))
    monkeypatch.setattr(transcribe_lesson_task, "delay", lambda *_: None)


@pytest.fixture
def act_as(client):
    """Переключает пользователя, от имени которого идут запросы."""

    def switch(user_id: int):
        app.dependency_overrides[get_any_user_id] = lambda: user_id
        return client

    yield switch
    app.dependency_overrides.pop(get_any_user_id, None)


async def _student(store, name: str) -> int:
    user = await store.user.add(
        return_model=True,
        email=f"student-{uuid.uuid4()}@example.com",
        roles=[UserRole.CLIENT.value],
    )
    await store.client.add(return_model=False, id=user.id, name=name)
    await store.session.commit()
    return user.id


async def _appointment(store, specialist_id, students, days_ago, cancelled=False):
    starts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).replace(
        minute=0, second=0, microsecond=0
    )
    slot = await store.availability_slot.add(
        return_model=True,
        specialist_id=specialist_id,
        starts_at=starts,
        ends_at=starts + timedelta(hours=1),
        status=SlotStatus.BOOKED,
        source=SlotSource.MANUAL,
    )
    appt = await store.appointment.add(
        return_model=True,
        slot_id=slot.id,
        is_group=len(students) > 1,
        cancelled_at=datetime.now(timezone.utc) if cancelled else None,
    )
    attendees = [(specialist_id, AppointmentRole.SPECIALIST)] + [
        (student, AppointmentRole.CLIENT) for student in students
    ]
    for user_id, role in attendees:
        await store.appointment_attendee.add(
            return_model=False, appointment_id=appt.id, user_id=user_id, role=role
        )
    await store.session.commit()


async def _set_transcript(store, lesson_id: str, **fields):
    transcript = await store.lesson_transcript.find_one_or_none(
        lesson_id=uuid.UUID(lesson_id)
    )
    await store.lesson_transcript.update(
        model_id=transcript.id, return_model=False, **fields
    )
    await store.session.commit()


def _upload(client, title="Урок"):
    resp = client.post(
        "/lessons/",
        data={"title": title},
        files={"file": ("lesson.mp3", b"fake-audio", "audio/mpeg")},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest_asyncio.fixture
async def people(store, specialist_id):
    """Специалист, двое учеников с общим групповым занятием и посторонние."""
    anna = await _student(store, "Анна")
    boris = await _student(store, "Борис")
    cancelled_only = await _student(store, "Отменённый")
    stranger = await _student(store, "Посторонний")
    await _appointment(store, specialist_id, [anna, boris], days_ago=3)
    await _appointment(store, specialist_id, [anna], days_ago=1)
    await _appointment(
        store, specialist_id, [cancelled_only], days_ago=2, cancelled=True
    )
    return {
        "specialist": specialist_id,
        "anna": anna,
        "boris": boris,
        "cancelled_only": cancelled_only,
        "stranger": stranger,
    }


@pytest.mark.asyncio
async def test_contacts_are_people_from_appointments_with_other_role(act_as, people):
    resp = act_as(people["specialist"]).get("/lessons/contacts")

    assert resp.status_code == 200
    contacts = resp.json()
    # Недавние сверху: у Анны последнее занятие вчера, у Бориса три дня назад.
    assert [c["user_id"] for c in contacts] == [people["anna"], people["boris"]]
    assert contacts[0]["name"] == "Анна"
    assert contacts[0]["last_appointment_at"]

    # Ученики одного группового занятия друг другу не собеседники.
    student_contacts = act_as(people["anna"]).get("/lessons/contacts").json()
    assert [c["user_id"] for c in student_contacts] == [people["specialist"]]
    assert student_contacts[0]["name"] == "T P"


@pytest.mark.asyncio
async def test_owner_shares_and_participant_reads(act_as, people):
    lesson_id = _upload(act_as(people["specialist"]))

    resp = act_as(people["specialist"]).post(
        f"/lessons/{lesson_id}/participants", json={"user_id": people["anna"]}
    )
    assert resp.status_code == 201
    assert resp.json() == [{"user_id": people["anna"], "name": "Анна"}]

    anna = act_as(people["anna"])
    lesson = anna.get(f"/lessons/{lesson_id}")
    assert lesson.status_code == 200
    assert lesson.json()["is_owner"] is False
    assert lesson.json()["transcript_status"] == "PENDING"
    assert anna.get(f"/lessons/{lesson_id}/transcript").status_code == 200


@pytest.mark.asyncio
async def test_participant_sees_finished_text(act_as, people, store):
    lesson_id = _upload(act_as(people["specialist"]))
    act_as(people["specialist"]).post(
        f"/lessons/{lesson_id}/participants", json={"user_id": people["anna"]}
    )
    segment = {"start": 0.0, "end": 2.5, "text": "Здравствуйте", "speaker": None}
    await _set_transcript(
        store,
        lesson_id,
        status=TranscriptStatus.DONE,
        language="ru",
        segments=[segment],
    )

    transcript = act_as(people["anna"]).get(f"/lessons/{lesson_id}/transcript").json()

    assert transcript["status"] == "DONE"
    assert transcript["segments"] == [segment]


@pytest.mark.asyncio
async def test_participant_does_not_see_failure_details(act_as, people, store):
    lesson_id = _upload(act_as(people["specialist"]))
    act_as(people["specialist"]).post(
        f"/lessons/{lesson_id}/participants", json={"user_id": people["anna"]}
    )
    await _set_transcript(
        store, lesson_id, status=TranscriptStatus.FAILED, error="decoder crashed"
    )

    owner_view = act_as(people["specialist"]).get(f"/lessons/{lesson_id}/transcript")
    assert owner_view.json()["status"] == "FAILED"
    assert owner_view.json()["error"] == "decoder crashed"

    anna = act_as(people["anna"])
    assert anna.get(f"/lessons/{lesson_id}").json()["transcript_status"] == "PENDING"
    participant_view = anna.get(f"/lessons/{lesson_id}/transcript").json()
    assert participant_view["status"] == "PENDING"
    assert participant_view["error"] is None
    assert participant_view["segments"] == []


@pytest.mark.asyncio
async def test_can_share_only_with_contacts(act_as, people):
    owner = act_as(people["specialist"])
    lesson_id = _upload(owner)
    url = f"/lessons/{lesson_id}/participants"

    for outsider in ("stranger", "cancelled_only"):
        assert owner.post(url, json={"user_id": people[outsider]}).status_code == 403
    assert owner.post(url, json={"user_id": people["specialist"]}).status_code == 422

    owner.post(url, json={"user_id": people["anna"]})
    again = owner.post(url, json={"user_id": people["anna"]})
    assert again.status_code == 201
    assert [p["user_id"] for p in again.json()] == [people["anna"]]


@pytest.mark.asyncio
async def test_stranger_sees_nothing(act_as, people):
    lesson_id = _upload(act_as(people["specialist"]))

    stranger = act_as(people["stranger"])
    assert stranger.get(f"/lessons/{lesson_id}").status_code == 404
    assert stranger.get(f"/lessons/{lesson_id}/transcript").status_code == 404
    assert stranger.get(f"/lessons/{lesson_id}/participants").status_code == 404
    assert stranger.post(f"/lessons/{lesson_id}/retry").status_code == 404
    add = stranger.post(
        f"/lessons/{lesson_id}/participants", json={"user_id": people["anna"]}
    )
    assert add.status_code == 404
    remove = stranger.delete(f"/lessons/{lesson_id}/participants/{people['stranger']}")
    assert remove.status_code == 404


@pytest.mark.asyncio
async def test_participant_cannot_do_owner_actions(act_as, people):
    owner = act_as(people["specialist"])
    lesson_id = _upload(owner)
    for student in ("anna", "boris"):
        owner.post(
            f"/lessons/{lesson_id}/participants", json={"user_id": people[student]}
        )

    anna = act_as(people["anna"])
    assert anna.post(f"/lessons/{lesson_id}/retry").status_code == 403
    assert anna.get(f"/lessons/{lesson_id}/participants").status_code == 403
    add = anna.post(
        f"/lessons/{lesson_id}/participants", json={"user_id": people["specialist"]}
    )
    assert add.status_code == 403
    other = anna.delete(f"/lessons/{lesson_id}/participants/{people['boris']}")
    assert other.status_code == 403


@pytest.mark.asyncio
async def test_owner_removes_participant(act_as, people):
    owner = act_as(people["specialist"])
    lesson_id = _upload(owner)
    owner.post(f"/lessons/{lesson_id}/participants", json={"user_id": people["anna"]})

    resp = owner.delete(f"/lessons/{lesson_id}/participants/{people['anna']}")

    assert resp.status_code == 204
    assert act_as(people["anna"]).get(f"/lessons/{lesson_id}").status_code == 404


@pytest.mark.asyncio
async def test_participant_removes_themselves(act_as, people):
    owner = act_as(people["specialist"])
    lesson_id = _upload(owner)
    owner.post(f"/lessons/{lesson_id}/participants", json={"user_id": people["anna"]})

    anna = act_as(people["anna"])
    assert (
        anna.delete(f"/lessons/{lesson_id}/participants/{people['anna']}").status_code
        == 204
    )
    assert anna.get(f"/lessons/{lesson_id}").status_code == 404
    assert (
        act_as(people["specialist"]).get(f"/lessons/{lesson_id}/participants").json()
        == []
    )


@pytest.mark.asyncio
async def test_shared_lessons_are_listed_separately(act_as, people):
    owner = act_as(people["specialist"])
    lesson_id = _upload(owner, title="Общий урок")
    owner.post(f"/lessons/{lesson_id}/participants", json={"user_id": people["anna"]})

    anna = act_as(people["anna"])
    shared = anna.get("/lessons/?scope=shared").json()
    assert [(item["id"], item["is_owner"]) for item in shared] == [(lesson_id, False)]
    assert anna.get("/lessons/").json() == []

    own = act_as(people["specialist"]).get("/lessons/?scope=own").json()
    assert [(item["id"], item["is_owner"]) for item in own] == [(lesson_id, True)]
    assert act_as(people["specialist"]).get("/lessons/?scope=shared").json() == []


@pytest.mark.asyncio
async def test_student_shares_own_recording_with_teacher(act_as, people):
    lesson_id = _upload(act_as(people["anna"]), title="Записала сама")

    resp = act_as(people["anna"]).post(
        f"/lessons/{lesson_id}/participants", json={"user_id": people["specialist"]}
    )

    assert resp.status_code == 201
    teacher = act_as(people["specialist"])
    assert [item["id"] for item in teacher.get("/lessons/?scope=shared").json()] == [
        lesson_id
    ]
    assert teacher.get(f"/lessons/{lesson_id}").json()["is_owner"] is False


def test_unknown_scope_is_rejected(act_as, specialist_id):
    assert act_as(specialist_id).get("/lessons/?scope=all").status_code == 422
