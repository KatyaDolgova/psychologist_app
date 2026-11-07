from datetime import datetime, timedelta, timezone

from tests.integration.api.dates import FREE_SLOTS_RANGE, SLOT_STARTS_AT


def test_list_specialist_free_slots(authed_specialist, specialist_id):
    # specialist creates a free slot
    authed_specialist.post(
        "/specialists/slots/",
        json={"starts_at": SLOT_STARTS_AT},
    )
    # any authed user can list them
    resp = authed_specialist.get(
        f"/specialists/{specialist_id}/free-slots/{FREE_SLOTS_RANGE}"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "FREE"


def test_free_slots_empty_for_unknown_specialist(authed_specialist):
    resp = authed_specialist.get(f"/specialists/9999999/free-slots/{FREE_SLOTS_RANGE}")
    assert resp.status_code == 200
    assert resp.json() == []


def test_free_slots_hide_past(authed_specialist, specialist_id):
    """Слоты, время которых уже прошло, не показываются клиенту."""
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    past = now - timedelta(hours=3)
    future = now + timedelta(hours=3)
    for starts_at in (past, future):
        authed_specialist.post(
            "/specialists/slots/",
            json={"starts_at": starts_at.isoformat()},
        )

    from_dt = (now - timedelta(days=1)).isoformat().replace("+", "%2B")
    to_dt = (now + timedelta(days=1)).isoformat().replace("+", "%2B")
    resp = authed_specialist.get(
        f"/specialists/{specialist_id}/free-slots/?from_dt={from_dt}&to_dt={to_dt}"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    starts_at = datetime.fromisoformat(body[0]["starts_at"])
    if starts_at.tzinfo is None:  # SQLite отдаёт время без часового пояса (UTC)
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    assert starts_at == future
