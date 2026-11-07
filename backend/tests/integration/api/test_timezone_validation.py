def test_patch_profile_rejects_bogus_timezone(authed_specialist):
    resp = authed_specialist.patch(
        "/specialists/profile/",
        json={"timezone": "Moscow"},
    )
    assert resp.status_code == 422


def test_patch_profile_rejects_empty_timezone(authed_specialist):
    resp = authed_specialist.patch(
        "/specialists/profile/",
        json={"timezone": ""},
    )
    assert resp.status_code == 422


def test_patch_profile_accepts_valid_iana_zone(authed_specialist):
    resp = authed_specialist.patch(
        "/specialists/profile/",
        json={"timezone": "Asia/Yekaterinburg"},
    )
    assert resp.status_code == 200


def test_patch_profile_accepts_utc(authed_specialist):
    resp = authed_specialist.patch(
        "/specialists/profile/",
        json={"timezone": "UTC"},
    )
    assert resp.status_code == 200
