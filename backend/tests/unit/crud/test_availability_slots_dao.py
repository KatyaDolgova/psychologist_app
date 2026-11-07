import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fastapi import HTTPException

from src.models import SlotSource, SlotStatus
from src.models.enums import UserRole

pytestmark = pytest.mark.asyncio


def _naive(dt: datetime) -> datetime:
    """Strip tzinfo so SQLite (test backend) and PG (prod) comparisons work uniformly.

    SQLite returns naive datetimes from TIMESTAMP columns; PG returns tz-aware.
    Tests assert on the underlying instant, not the tz attribute.
    """
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


@pytest_asyncio.fixture
async def specialist_user(store):
    """Создаёт тестового пользователя-специалиста и возвращает его id."""
    user = await store.user.add(
        return_model=True,
        email=f"specialist-{uuid.uuid4()}@example.com",
        roles=[UserRole.SPECIALIST.value],
    )
    return user.id


async def test_add_slot_returns_row(store, specialist_user):
    starts = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    ends = starts + timedelta(hours=1)

    slot = await store.availability_slot.add(
        return_model=True,
        specialist_id=specialist_user,
        starts_at=starts,
        ends_at=ends,
        status=SlotStatus.FREE,
        source=SlotSource.MANUAL,
    )

    assert slot.id is not None
    assert slot.status == SlotStatus.FREE
    assert _naive(slot.starts_at) == _naive(starts)


async def test_bulk_insert_ignore_conflicts_skips_duplicates(store, specialist_user):
    starts = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    rows = [
        {
            "specialist_id": specialist_user,
            "starts_at": starts,
            "ends_at": starts + timedelta(hours=1),
            "status": SlotStatus.FREE,
            "source": SlotSource.TEMPLATE,
        },
        {
            "specialist_id": specialist_user,
            "starts_at": starts,
            "ends_at": starts + timedelta(hours=1),
            "status": SlotStatus.FREE,
            "source": SlotSource.TEMPLATE,
        },
    ]
    created = await store.availability_slot.bulk_insert_ignore_conflicts(rows)
    assert created == 1


async def test_list_in_range_filters_status_and_window(store, specialist_user):
    base = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    # Free in range
    await store.availability_slot.add(
        specialist_id=specialist_user,
        starts_at=base,
        ends_at=base + timedelta(hours=1),
        status=SlotStatus.FREE,
        source=SlotSource.MANUAL,
    )
    # Booked in range (must be excluded by status filter)
    await store.availability_slot.add(
        specialist_id=specialist_user,
        starts_at=base + timedelta(hours=2),
        ends_at=base + timedelta(hours=3),
        status=SlotStatus.BOOKED,
        source=SlotSource.MANUAL,
    )
    # Free outside range (must be excluded by window)
    await store.availability_slot.add(
        specialist_id=specialist_user,
        starts_at=base + timedelta(days=30),
        ends_at=base + timedelta(days=30, hours=1),
        status=SlotStatus.FREE,
        source=SlotSource.MANUAL,
    )

    found = await store.availability_slot.list_in_range(
        specialist_id=specialist_user,
        from_dt=base - timedelta(hours=1),
        to_dt=base + timedelta(hours=4),
        status=SlotStatus.FREE,
    )
    assert len(found) == 1
    assert _naive(found[0].starts_at) == _naive(base)


async def test_unique_constraint_on_specialist_starts(store, specialist_user):
    starts = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    await store.availability_slot.add(
        specialist_id=specialist_user,
        starts_at=starts,
        ends_at=starts + timedelta(hours=1),
        status=SlotStatus.FREE,
        source=SlotSource.MANUAL,
    )
    # @handle_db_errors wraps IntegrityError into HTTPException(409)
    with pytest.raises(HTTPException) as exc_info:
        await store.availability_slot.add(
            specialist_id=specialist_user,
            starts_at=starts,
            ends_at=starts + timedelta(hours=2),
            status=SlotStatus.FREE,
            source=SlotSource.MANUAL,
        )
    assert exc_info.value.status_code == 409


async def test_try_book_returns_specialist_id_on_success(store, specialist_user):
    starts = (datetime.now(timezone.utc) + timedelta(days=7)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    slot = await store.availability_slot.add(
        return_model=True,
        specialist_id=specialist_user,
        starts_at=starts,
        ends_at=starts + timedelta(hours=1),
        status=SlotStatus.FREE,
        source=SlotSource.MANUAL,
    )
    specialist_id = await store.availability_slot.try_book(slot.id)
    assert specialist_id == specialist_user


async def test_try_book_returns_none_when_started(store, specialist_user):
    starts = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(
        second=0, microsecond=0
    )
    slot = await store.availability_slot.add(
        return_model=True,
        specialist_id=specialist_user,
        starts_at=starts,
        ends_at=starts + timedelta(hours=1),
        status=SlotStatus.FREE,
        source=SlotSource.MANUAL,
    )
    assert await store.availability_slot.try_book(slot.id) is None


async def test_try_book_returns_none_when_not_free(store, specialist_user):
    starts = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    slot = await store.availability_slot.add(
        return_model=True,
        specialist_id=specialist_user,
        starts_at=starts,
        ends_at=starts + timedelta(hours=1),
        status=SlotStatus.BOOKED,
        source=SlotSource.MANUAL,
    )
    assert await store.availability_slot.try_book(slot.id) is None


async def test_try_book_returns_none_for_missing(store):
    assert await store.availability_slot.try_book(uuid.uuid4()) is None


async def test_try_release_returns_true_when_booked(store, specialist_user):
    starts = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    slot = await store.availability_slot.add(
        return_model=True,
        specialist_id=specialist_user,
        starts_at=starts,
        ends_at=starts + timedelta(hours=1),
        status=SlotStatus.BOOKED,
        source=SlotSource.MANUAL,
    )
    assert await store.availability_slot.try_release(slot.id) is True


async def test_try_release_returns_false_when_not_booked(store, specialist_user):
    starts = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    slot = await store.availability_slot.add(
        return_model=True,
        specialist_id=specialist_user,
        starts_at=starts,
        ends_at=starts + timedelta(hours=1),
        status=SlotStatus.FREE,
        source=SlotSource.MANUAL,
    )
    assert await store.availability_slot.try_release(slot.id) is False


async def test_try_specialist_cancel_checks_ownership_and_status(
    store, specialist_user
):
    starts = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    slot = await store.availability_slot.add(
        return_model=True,
        specialist_id=specialist_user,
        starts_at=starts,
        ends_at=starts + timedelta(hours=1),
        status=SlotStatus.BOOKED,
        source=SlotSource.MANUAL,
    )
    # Wrong specialist
    assert await store.availability_slot.try_specialist_cancel(slot.id, 999999) is False
    # Right specialist
    assert (
        await store.availability_slot.try_specialist_cancel(slot.id, specialist_user)
        is True
    )
    # Already CANCELLED — second attempt fails
    assert (
        await store.availability_slot.try_specialist_cancel(slot.id, specialist_user)
        is False
    )


async def test_delete_stale_free_removes_only_old_free(store, specialist_user):
    now = datetime.now(timezone.utc)
    # Old FREE — should be deleted
    old_free = await store.availability_slot.add(
        return_model=True,
        specialist_id=specialist_user,
        starts_at=now - timedelta(days=30),
        ends_at=now - timedelta(days=30) + timedelta(hours=1),
        status=SlotStatus.FREE,
        source=SlotSource.MANUAL,
    )
    # Old BOOKED — must be kept
    old_booked = await store.availability_slot.add(
        return_model=True,
        specialist_id=specialist_user,
        starts_at=now - timedelta(days=20),
        ends_at=now - timedelta(days=20) + timedelta(hours=1),
        status=SlotStatus.BOOKED,
        source=SlotSource.MANUAL,
    )
    # Future FREE — must be kept
    future_free = await store.availability_slot.add(
        return_model=True,
        specialist_id=specialist_user,
        starts_at=now + timedelta(days=10),
        ends_at=now + timedelta(days=10, hours=1),
        status=SlotStatus.FREE,
        source=SlotSource.MANUAL,
    )
    ids = (old_free.id, old_booked.id, future_free.id)
    store.session.expunge_all()

    cutoff = now - timedelta(days=7)
    deleted = await store.availability_slot.delete_stale_free(cutoff=cutoff)

    # Очистка глобальная: в общей тестовой БД могут лежать старые слоты
    # других тестов, поэтому проверяем судьбу своих слотов, а не точный счётчик.
    assert deleted >= 1
    old_free_id, old_booked_id, future_free_id = ids
    assert await store.availability_slot.find_by_id(model_id=old_free_id) is None
    assert await store.availability_slot.find_by_id(model_id=old_booked_id)
    assert await store.availability_slot.find_by_id(model_id=future_free_id)


async def test_last_slot_date_returns_latest(store, specialist_user):
    base = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    await store.availability_slot.add(
        specialist_id=specialist_user,
        starts_at=base,
        ends_at=base + timedelta(hours=1),
        status=SlotStatus.FREE,
        source=SlotSource.MANUAL,
    )
    await store.availability_slot.add(
        specialist_id=specialist_user,
        starts_at=base + timedelta(days=5),
        ends_at=base + timedelta(days=5, hours=1),
        status=SlotStatus.FREE,
        source=SlotSource.MANUAL,
    )
    last = await store.availability_slot.last_slot_date(specialist_id=specialist_user)
    assert _naive(last) == _naive(base + timedelta(days=5))


async def test_last_slot_date_returns_none_for_empty(store, specialist_user):
    last = await store.availability_slot.last_slot_date(specialist_id=specialist_user)
    assert last is None


async def test_set_status_updates_slot(store, specialist_user):
    base = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    slot = await store.availability_slot.add(
        return_model=True,
        specialist_id=specialist_user,
        starts_at=base,
        ends_at=base + timedelta(hours=1),
        status=SlotStatus.FREE,
        source=SlotSource.MANUAL,
    )
    await store.availability_slot.set_status(slot.id, SlotStatus.BOOKED)
    refreshed = await store.availability_slot.find_by_id(model_id=slot.id)
    assert refreshed.status == SlotStatus.BOOKED
