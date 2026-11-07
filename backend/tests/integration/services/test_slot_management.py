import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from src.core.exceptions import (
    NotSlotOwnerError,
    SlotCollisionError,
    SlotNotFoundError,
    SlotNotFreeError,
)
from src.models import AvailabilitySlot, SlotSource, SlotStatus
from src.models.enums import UserRole
from src.services.availability.slot_management import SlotManagementService

pytestmark = pytest.mark.asyncio


def _naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


async def _make_specialist(store) -> int:
    user = await store.user.add(
        return_model=True,
        email=f"specialist-{uuid.uuid4()}@example.com",
        roles=[UserRole.SPECIALIST.value],
    )
    await store.specialist.add(
        return_model=False,
        id=user.id,
        first_name="T",
        last_name="P",
        timezone="Europe/Moscow",
        session_duration_minutes=60,
    )
    return user.id


@pytest_asyncio.fixture
async def specialist(store):
    return await _make_specialist(store)


@pytest_asyncio.fixture
async def other_specialist(store):
    return await _make_specialist(store)


async def test_create_one_off_slot_uses_profile_duration(store, specialist):
    service = SlotManagementService(store=store)
    starts = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    slot = await service.create_one_off(specialist_id=specialist, starts_at=starts)
    assert slot.source == SlotSource.MANUAL
    assert slot.status == SlotStatus.FREE
    assert _naive(slot.ends_at) == _naive(starts + timedelta(hours=1))


async def test_create_one_off_collision_raises(store, specialist):
    service = SlotManagementService(store=store)
    starts = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    await service.create_one_off(specialist_id=specialist, starts_at=starts)
    with pytest.raises(SlotCollisionError):
        await service.create_one_off(specialist_id=specialist, starts_at=starts)


async def test_patch_slot_preserves_duration(store, specialist):
    service = SlotManagementService(store=store)
    starts = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    slot = await service.create_one_off(specialist_id=specialist, starts_at=starts)
    new_starts = datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc)
    edited = await service.update_starts_at(
        specialist_id=specialist, slot_id=slot.id, new_starts_at=new_starts
    )
    assert _naive(edited.starts_at) == _naive(new_starts)
    assert _naive(edited.ends_at) == _naive(new_starts + timedelta(hours=1))


async def test_patch_slot_not_free_raises(store, specialist):
    service = SlotManagementService(store=store)
    starts = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    slot = await service.create_one_off(specialist_id=specialist, starts_at=starts)
    await store.availability_slot.set_status(slot.id, SlotStatus.BOOKED)
    with pytest.raises(SlotNotFreeError):
        await service.update_starts_at(
            specialist_id=specialist,
            slot_id=slot.id,
            new_starts_at=datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc),
        )


async def test_patch_slot_not_owner_raises(store, specialist, other_specialist):
    service = SlotManagementService(store=store)
    starts = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    slot = await service.create_one_off(specialist_id=specialist, starts_at=starts)
    with pytest.raises(NotSlotOwnerError):
        await service.update_starts_at(
            specialist_id=other_specialist,
            slot_id=slot.id,
            new_starts_at=datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc),
        )


async def test_delete_slot_owner_only(store, specialist, other_specialist):
    service = SlotManagementService(store=store)
    starts = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    slot = await service.create_one_off(specialist_id=specialist, starts_at=starts)
    with pytest.raises(NotSlotOwnerError):
        await service.delete(specialist_id=other_specialist, slot_id=slot.id)


async def test_delete_nonexistent_raises(store, specialist):
    service = SlotManagementService(store=store)
    with pytest.raises(SlotNotFoundError):
        await service.delete(specialist_id=specialist, slot_id=uuid.uuid4())


async def test_delete_free_slot_succeeds(store, specialist):
    service = SlotManagementService(store=store)
    starts = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    slot = await service.create_one_off(specialist_id=specialist, starts_at=starts)
    await service.delete(specialist_id=specialist, slot_id=slot.id)
    refreshed = await store.session.get(AvailabilitySlot, slot.id)
    assert refreshed is None


async def test_delete_booked_slot_raises(store, specialist):
    service = SlotManagementService(store=store)
    starts = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    slot = await service.create_one_off(specialist_id=specialist, starts_at=starts)
    await store.availability_slot.set_status(slot.id, SlotStatus.BOOKED)
    with pytest.raises(SlotNotFreeError):
        await service.delete(specialist_id=specialist, slot_id=slot.id)
