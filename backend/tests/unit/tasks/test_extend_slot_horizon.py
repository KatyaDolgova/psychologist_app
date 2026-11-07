import uuid
from datetime import date, time, timedelta

import pytest
import pytest_asyncio

from src.models.enums import DayOfWeek, UserRole
from src.tasks.extend_slot_horizon import extend_horizon_for_specialist

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def specialist_with_template(store):
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
    await store.working_hours.add(
        return_model=False,
        specialist_id=user.id,
        day_of_week=DayOfWeek.MONDAY,
        start_time=time(9, 0),
        end_time=time(12, 0),
        is_active=True,
    )
    return user.id


async def test_extend_horizon_creates_slots_up_to_target(
    store, specialist_with_template
):
    target = date.today() + timedelta(days=14)
    created = await extend_horizon_for_specialist(
        store=store, specialist_id=specialist_with_template, target=target
    )
    assert created > 0


async def test_extend_horizon_target_in_past_returns_zero(
    store, specialist_with_template
):
    target = date.today() - timedelta(days=5)
    created = await extend_horizon_for_specialist(
        store=store, specialist_id=specialist_with_template, target=target
    )
    # No matter what (no slots yet, but target is past) — should be 0
    # because the SlotGenerationService rejects from_date > to_date naturally
    assert created == 0


async def test_extend_horizon_idempotent(store, specialist_with_template):
    target = date.today() + timedelta(days=14)
    first = await extend_horizon_for_specialist(
        store=store, specialist_id=specialist_with_template, target=target
    )
    second = await extend_horizon_for_specialist(
        store=store, specialist_id=specialist_with_template, target=target
    )
    assert first > 0
    assert second == 0  # all already generated; from_date > target
