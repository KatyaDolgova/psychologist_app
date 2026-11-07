from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from src.core.dependencies import get_any_user_id, get_store
from src.crud import Store
from src.models.enums.slots import SlotStatus
from src.schemas.availability import AvailabilitySlotSchema

router = APIRouter(tags=["Specialists Public Slots"])


@router.get(
    "/{specialist_id}/free-slots/",
    summary="Свободные слоты специалиста",
    description=(
        "Возвращает список FREE-слотов указанного специалиста в окне [from_dt, to_dt). "
        "Слоты, время которых уже наступило, не возвращаются. "
        "Доступно любому аутентифицированному пользователю."
    ),
)
async def list_free_slots(
    specialist_id: int,
    from_dt: datetime = Query(...),
    to_dt: datetime = Query(...),
    _user: int = Depends(get_any_user_id),
    store: Store = Depends(get_store),
) -> list[AvailabilitySlotSchema]:
    if from_dt.tzinfo is None:
        from_dt = from_dt.replace(tzinfo=timezone.utc)
    # На прошедшее время записаться нельзя, поэтому и показывать его незачем.
    from_dt = max(from_dt, datetime.now(timezone.utc))
    slots = await store.availability_slot.list_in_range(
        specialist_id=specialist_id,
        from_dt=from_dt,
        to_dt=to_dt,
        status=SlotStatus.FREE,
    )
    return [AvailabilitySlotSchema.model_validate(s) for s in slots]
