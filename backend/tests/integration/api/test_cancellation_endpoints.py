from tests.integration.api.dates import FREE_SLOTS_RANGE, SLOT_STARTS_AT


def test_client_cancels_returns_slot_to_free(
    authed_specialist, authed_client, specialist_id
):
    create_slot = authed_specialist.post(
        "/specialists/slots/",
        json={"starts_at": SLOT_STARTS_AT},
    )
    slot_id = create_slot.json()["id"]
    book = authed_client.post("/user/appointments/", json={"slot_id": slot_id})
    appt_id = book.json()["id"]
    cancel = authed_client.delete(f"/user/appointments/{appt_id}")
    assert cancel.status_code == 204

    free = authed_client.get(
        f"/specialists/{specialist_id}/free-slots/{FREE_SLOTS_RANGE}"
    )
    assert len(free.json()) == 1


def test_specialist_cancels_marks_slot_cancelled(
    authed_specialist, authed_client, specialist_id
):
    create_slot = authed_specialist.post(
        "/specialists/slots/",
        json={"starts_at": SLOT_STARTS_AT},
    )
    slot_id = create_slot.json()["id"]
    authed_client.post("/user/appointments/", json={"slot_id": slot_id})
    specialist_cancel = authed_specialist.post(
        f"/specialists/slots/{slot_id}/cancel",
        json={"reason": "тест"},
    )
    assert specialist_cancel.status_code == 204

    free = authed_client.get(
        f"/specialists/{specialist_id}/free-slots/{FREE_SLOTS_RANGE}"
    )
    assert len(free.json()) == 0


def test_double_cancel_returns_409(authed_specialist, authed_client):
    create_slot = authed_specialist.post(
        "/specialists/slots/",
        json={"starts_at": SLOT_STARTS_AT},
    )
    slot_id = create_slot.json()["id"]
    book = authed_client.post("/user/appointments/", json={"slot_id": slot_id})
    appt_id = book.json()["id"]
    authed_client.delete(f"/user/appointments/{appt_id}")
    resp = authed_client.delete(f"/user/appointments/{appt_id}")
    assert resp.status_code == 409
