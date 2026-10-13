"""Даты для API-тестов слотов.

Запись на прошедшее время запрещена, поэтому тесты берут день в будущем,
а не фиксированную дату. Понедельник — потому что e2e-тест генерирует
слоты по шаблону на MONDAY.
"""

from datetime import date, timedelta


def _next_monday(min_days_ahead: int = 7) -> date:
    day = date.today() + timedelta(days=min_days_ahead)
    return day + timedelta(days=(7 - day.weekday()) % 7)


DAY = _next_monday()
NEXT_DAY = DAY + timedelta(days=1)

SLOT_STARTS_AT = f"{DAY.isoformat()}T09:00:00+00:00"
FREE_SLOTS_RANGE = (
    f"?from_dt={DAY.isoformat()}T00:00:00%2B00:00"
    f"&to_dt={NEXT_DAY.isoformat()}T00:00:00%2B00:00"
)
