from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import aliased

from src.core.wrapper import handle_db_errors
from src.crud.impl.base import BaseDAO
from src.models import (
    Appointment,
    AppointmentAttendee,
    AvailabilitySlot,
    ClientProfile,
    SpecialistProfile,
)
from src.models.lesson_participant import LessonParticipant


def display_name(user_id_column):
    """Имя пользователя для списков: имя ученика или имя и фамилия специалиста."""
    cp = aliased(ClientProfile)
    sp = aliased(SpecialistProfile)
    name = func.coalesce(cp.name, sp.first_name + " " + sp.last_name)
    joins = [(cp, cp.id == user_id_column), (sp, sp.id == user_id_column)]
    return name, joins


class LessonParticipantDAO(BaseDAO):
    """DAO для участников урока: тех, с кем автор поделился записью."""

    model = LessonParticipant

    @handle_db_errors
    async def is_participant(self, lesson_id: UUID, user_id: int) -> bool:
        query = select(
            select(LessonParticipant.id)
            .where(
                LessonParticipant.lesson_id == lesson_id,
                LessonParticipant.user_id == user_id,
            )
            .exists()
        )
        result = await self.session.execute(query)
        return bool(result.scalar())

    @handle_db_errors
    async def find_for_lesson(self, lesson_id: UUID):
        """Участники урока с именами, в порядке добавления."""
        name, joins = display_name(LessonParticipant.user_id)
        query = select(LessonParticipant.user_id, name.label("name"))
        for profile, condition in joins:
            query = query.outerjoin(profile, condition)
        query = query.where(LessonParticipant.lesson_id == lesson_id).order_by(
            LessonParticipant.created_at, LessonParticipant.user_id
        )
        result = await self.session.execute(query)
        return result.mappings().all()

    def _contacts_query(self, user_id: int, only_id: int | None = None):
        """Собеседники по неотменённым занятиям: у кого на общем занятии другая роль.

        Для специалиста это его ученики, для ученика его преподаватели. Ученики одного
        группового занятия друг другу не собеседники: роль у них одинаковая.
        only_id оставляет в выборке одного собеседника.
        """
        me = aliased(AppointmentAttendee)
        other = aliased(AppointmentAttendee)
        name, joins = display_name(other.user_id)
        query = (
            select(
                other.user_id,
                name.label("name"),
                func.max(AvailabilitySlot.starts_at).label("last_appointment_at"),
            )
            .select_from(me)
            .join(other, other.appointment_id == me.appointment_id)
            .join(Appointment, Appointment.id == me.appointment_id)
            .join(AvailabilitySlot, AvailabilitySlot.id == Appointment.slot_id)
        )
        for profile, condition in joins:
            query = query.outerjoin(profile, condition)
        query = query.where(
            me.user_id == user_id,
            other.role != me.role,
            Appointment.cancelled_at.is_(None),
        )
        if only_id is not None:
            query = query.where(other.user_id == only_id)
        return query.group_by(other.user_id, name)

    @handle_db_errors
    async def find_contacts(self, user_id: int):
        """С кем пользователь может поделиться уроком, недавние сверху."""
        query = self._contacts_query(user_id).order_by(
            func.max(AvailabilitySlot.starts_at).desc()
        )
        result = await self.session.execute(query)
        return result.mappings().all()

    @handle_db_errors
    async def is_contact(self, user_id: int, other_id: int) -> bool:
        result = await self.session.execute(
            self._contacts_query(user_id, only_id=other_id).limit(1)
        )
        return result.first() is not None

    @handle_db_errors
    async def remove(self, lesson_id: UUID, user_id: int) -> bool:
        """Убирает участника; возвращает False, если его и не было."""
        result = await self.session.execute(
            delete(LessonParticipant).where(
                LessonParticipant.lesson_id == lesson_id,
                LessonParticipant.user_id == user_id,
            )
        )
        return result.rowcount > 0
