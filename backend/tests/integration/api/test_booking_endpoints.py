from datetime import datetime, timedelta, timezone

import pytest

from src.models import SlotSource, SlotStatus
from src.models.enums.appointments import AppointmentRole
from tests.integration.api.dates import DAY, SLOT_STARTS_AT
from tests.utils import requires_postgres


def test_book_slot_via_api(authed_psy, authed_client, psy_id):
    create_slot = authed_psy.post(
        "/psychologists/slots/",
        json={"starts_at": SLOT_STARTS_AT},
    )
    slot_id = create_slot.json()["id"]
    resp = authed_client.post("/user/appointments/", json={"slot_id": slot_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["slot_id"] == slot_id
    assert f"{DAY.isoformat()}T09:00" in data["start_at"]


def test_double_book_returns_409(authed_psy, authed_client):
    create = authed_psy.post(
        "/psychologists/slots/",
        json={"starts_at": SLOT_STARTS_AT},
    )
    slot_id = create.json()["id"]
    r1 = authed_client.post("/user/appointments/", json={"slot_id": slot_id})
    assert r1.status_code == 200
    r2 = authed_client.post("/user/appointments/", json={"slot_id": slot_id})
    assert r2.status_code == 409


def test_book_missing_slot_returns_404(authed_client):
    import uuid

    resp = authed_client.post(
        "/user/appointments/", json={"slot_id": str(uuid.uuid4())}
    )
    assert resp.status_code == 404


def test_book_past_slot_returns_409(authed_psy, authed_client):
    """На слот, время которого уже прошло, записаться нельзя."""
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(
        minute=0, second=0, microsecond=0
    )
    create = authed_psy.post(
        "/psychologists/slots/",
        json={"starts_at": past.isoformat()},
    )
    assert create.status_code == 200
    slot_id = create.json()["id"]

    resp = authed_client.post("/user/appointments/", json={"slot_id": slot_id})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Нельзя записаться на прошедшее время"


@requires_postgres
@pytest.mark.asyncio
async def test_client_sees_completed_appointments(
    store, psy_id, client_id, authed_client
):
    """Завершённая запись возвращается клиенту при is_upcoming=false."""
    starts = (datetime.now(timezone.utc) - timedelta(days=1)).replace(
        minute=0, second=0, microsecond=0
    )
    slot = await store.availability_slot.add(
        return_model=True,
        psychologist_id=psy_id,
        starts_at=starts,
        ends_at=starts + timedelta(hours=1),
        status=SlotStatus.BOOKED,
        source=SlotSource.MANUAL,
    )
    appt = await store.appointment.add(
        return_model=True, slot_id=slot.id, is_group=False
    )
    for user_id, role in (
        (client_id, AppointmentRole.CLIENT),
        (psy_id, AppointmentRole.PSYCHOLOGIST),
    ):
        await store.appointment_attendee.add(
            return_model=False, appointment_id=appt.id, user_id=user_id, role=role
        )
    await store.session.commit()

    upcoming = authed_client.get("/user/appointments/")
    assert upcoming.status_code == 200
    assert upcoming.json() == []

    completed = authed_client.get("/user/appointments/?is_upcoming=false")
    assert completed.status_code == 200
    assert [a["id"] for a in completed.json()] == [str(appt.id)]
