from tests.integration.api.dates import DAY, FREE_SLOTS_RANGE


def test_full_booking_happy_path(authed_psy, authed_client, psy_id):
    """End-to-end: template → generate → list free → book → cancel."""
    # 1. Psy sets template
    r = authed_psy.put(
        "/psychologists/template/",
        json={
            "ranges": [
                {
                    "day_of_week": "MONDAY",
                    "start_time": "09:00:00",
                    "end_time": "12:00:00",
                    "is_active": True,
                }
            ]
        },
    )
    assert r.status_code == 200

    # 2. Psy generates slots
    g = authed_psy.post(f"/psychologists/slots/generate?from_date={DAY}&to_date={DAY}")
    assert g.status_code == 200
    assert g.json()["created"] == 3

    # 3. Client lists free slots
    f = authed_client.get(f"/psychologists/{psy_id}/free-slots/{FREE_SLOTS_RANGE}")
    assert f.status_code == 200
    free_slots = f.json()
    assert len(free_slots) == 3

    # 4. Client books one
    book = authed_client.post(
        "/user/appointments/",
        json={"slot_id": free_slots[0]["id"]},
    )
    assert book.status_code == 200

    # 5. The booked slot disappears from free listing
    f2 = authed_client.get(f"/psychologists/{psy_id}/free-slots/{FREE_SLOTS_RANGE}")
    assert len(f2.json()) == 2

    # 6. Template-edit doesn't disturb existing slots
    authed_psy.put(
        "/psychologists/template/",
        json={
            "ranges": [
                {
                    "day_of_week": "TUESDAY",
                    "start_time": "10:00:00",
                    "end_time": "11:00:00",
                    "is_active": True,
                }
            ]
        },
    )
    f3 = authed_client.get(f"/psychologists/{psy_id}/free-slots/{FREE_SLOTS_RANGE}")
    # still 2 free Monday slots — template edit didn't delete them
    assert len(f3.json()) == 2

    # 7. Client cancels booking — slot returns to FREE
    appt_id = book.json()["id"]
    cancel = authed_client.delete(f"/user/appointments/{appt_id}")
    assert cancel.status_code == 204
    f4 = authed_client.get(f"/psychologists/{psy_id}/free-slots/{FREE_SLOTS_RANGE}")
    assert len(f4.json()) == 3  # back to 3
