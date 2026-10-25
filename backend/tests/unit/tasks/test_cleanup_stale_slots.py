import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from src.models import SlotSource, SlotStatus
from src.models.enums import UserRole
from src.tasks.cleanup_stale_slots import cleanup_stale_free

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def psy(store):
    user = await store.user.add(
        return_model=True,
        email=f"psy-{uuid.uuid4()}@example.com",
        roles=[UserRole.PSYCHOLOGIST.value],
    )
    return user.id


async def _add_slot(store, psy, starts_at, status):
    return await store.availability_slot.add(
        return_model=True,
        psychologist_id=psy,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        status=status,
        source=SlotSource.MANUAL,
    )


async def test_cleanup_deletes_only_old_free_slots(store, psy):
    now = datetime.now(timezone.utc)
    # Old FREE — should be deleted
    old_free = await _add_slot(store, psy, now - timedelta(days=30), SlotStatus.FREE)
    # Must be kept: old BOOKED, future FREE, recent FREE inside the 7-day buffer
    kept = [
        await _add_slot(store, psy, now - timedelta(days=20), SlotStatus.BOOKED),
        await _add_slot(store, psy, now + timedelta(days=10), SlotStatus.FREE),
        await _add_slot(store, psy, now - timedelta(days=3), SlotStatus.FREE),
    ]
    old_free_id = old_free.id
    kept_ids = [slot.id for slot in kept]
    store.session.expunge_all()

    deleted = await cleanup_stale_free(store=store)

    # Очистка глобальная: в общей тестовой БД могут лежать старые слоты
    # других тестов, поэтому проверяем судьбу своих слотов, а не точный счётчик.
    assert deleted >= 1
    assert await store.availability_slot.find_by_id(model_id=old_free_id) is None
    for slot_id in kept_ids:
        assert await store.availability_slot.find_by_id(model_id=slot_id)


async def test_cleanup_second_run_returns_zero(store):
    """После очистки старых свободных слотов не остаётся — повтор ничего не удаляет."""
    await cleanup_stale_free(store=store)
    deleted = await cleanup_stale_free(store=store)
    assert deleted == 0
