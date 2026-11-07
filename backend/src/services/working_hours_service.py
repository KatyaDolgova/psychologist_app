from fastapi import Depends

from src.core.dependencies import get_store
from src.core.exceptions import TemplateRangeOverlapError
from src.crud import Store
from src.models import SpecialistWorkingHours
from src.schemas.working_hours import TemplateRangeInput


class WorkingHoursService:
    """Сервис управления недельным шаблоном рабочих часов специалиста.

    Шаблон представляет собой набор диапазонов (день недели + start_time + end_time).
    В одном дне может быть несколько диапазонов (например, утро + вечер).
    Сервис гарантирует, что диапазоны в одном дне не пересекаются.

    Шаблон НЕ затрагивает уже сгенерированные слоты — для применения изменений
    специалист должен явно вызвать `POST /specialists/slots/generate`.
    """

    def __init__(self, store: Store = Depends(get_store)):
        self._store = store

    async def get_template(self, specialist_id: int) -> list[SpecialistWorkingHours]:
        """Возвращает все диапазоны шаблона специалиста."""
        return await self._store.working_hours.get_by_specialist(
            specialist_id=specialist_id
        )

    async def replace_template(
        self,
        specialist_id: int,
        ranges: list[TemplateRangeInput],
    ) -> list[SpecialistWorkingHours]:
        """Атомарно заменяет шаблон специалиста.

        Сначала валидирует отсутствие пересечений в одном дне.
        Затем удаляет все существующие диапазоны и вставляет новые.
        НЕ затрагивает сгенерированные слоты.

        Raises:
            TemplateRangeOverlapError: если два диапазона в одном дне пересекаются.
        """
        self._validate_no_overlaps(ranges)

        await self._store.working_hours.delete_all_for_specialist(
            specialist_id=specialist_id
        )
        for r in ranges:
            await self._store.working_hours.add(
                return_model=False,
                specialist_id=specialist_id,
                day_of_week=r.day_of_week,
                start_time=r.start_time,
                end_time=r.end_time,
                is_active=r.is_active,
            )
        return await self.get_template(specialist_id=specialist_id)

    @staticmethod
    def _validate_no_overlaps(ranges: list[TemplateRangeInput]) -> None:
        """Проверяет, что в одном дне недели нет пересекающихся диапазонов."""
        by_day: dict = {}
        for r in ranges:
            by_day.setdefault(r.day_of_week, []).append(r)
        for day, group in by_day.items():
            sorted_group = sorted(group, key=lambda r: r.start_time)
            for prev, curr in zip(sorted_group, sorted_group[1:]):
                if curr.start_time < prev.end_time:
                    raise TemplateRangeOverlapError(
                        detail=f"Диапазоны в дне {day.value} пересекаются"
                    )
