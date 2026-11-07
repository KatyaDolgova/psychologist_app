def test_patch_profile_updates_timezone_and_duration(authed_specialist):
    resp = authed_specialist.patch(
        "/specialists/profile/",
        json={
            "timezone": "Asia/Yekaterinburg",
            "session_duration_minutes": 90,
        },
    )
    assert resp.status_code == 200

    get_resp = authed_specialist.get("/specialists/profile/")
    body = get_resp.json()
    assert body["timezone"] == "Asia/Yekaterinburg"
    assert body["session_duration_minutes"] == 90


def test_patch_profile_rejects_invalid_duration(authed_specialist):
    resp = authed_specialist.patch(
        "/specialists/profile/",
        json={"session_duration_minutes": 0},
    )
    assert resp.status_code == 422


def test_patch_profile_rejects_excessive_duration(authed_specialist):
    resp = authed_specialist.patch(
        "/specialists/profile/",
        json={"session_duration_minutes": 1000},
    )
    assert resp.status_code == 422
