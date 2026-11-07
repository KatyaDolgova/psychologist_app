from fastapi import Depends, HTTPException

from src.config import settings
from src.core.dependencies import get_store
from src.crud import Store
from src.schemas.clients import ClientProfileForSpecialist, SpecialistClientSchema


class SpecialistClientsService:
    def __init__(self, store: Store = Depends(get_store)):
        self._store = store

    async def get_clients(
        self,
        specialist_id: int,
        limit: int = 25,
        offset: int = 0,
        name: str | None = None,
    ) -> list[SpecialistClientSchema]:
        rows = await self._store.appointment_attendee.get_specialist_clients(
            specialist_id=specialist_id,
            limit=limit,
            offset=offset,
            name=name,
        )
        return [
            SpecialistClientSchema(
                client_id=row["client_id"],
                name=row["name"] if row["name"] else "Anonymous",
                avatar=(settings.STATIC_BASE_URL + row["avatar"])
                if row["avatar"]
                else None,
                first_session=row["first_session"].date(),
                total_sessions=row["total_sessions"],
            )
            for row in rows
        ]

    async def get_client_profile(
        self, specialist_id: int, user_id: int
    ) -> ClientProfileForSpecialist:
        has_appointment = await self._store.appointment_attendee.has_shared_appointment(
            user_id_a=specialist_id, user_id_b=user_id
        )
        if not has_appointment:
            raise HTTPException(status_code=403, detail="Нет записей с этим клиентом")

        client = await self._store.client.find_one_or_none(id=user_id)
        if not client:
            raise HTTPException(status_code=404, detail="Клиент не найден")

        avatar = None
        if client.avatar:
            avatar = settings.STATIC_BASE_URL + client.avatar

        return ClientProfileForSpecialist(
            id=client.id,
            name=client.name,
            age=client.age,
            gender=client.gender,
            birth_date=client.birth_date,
            avatar=avatar,
            emotions=client.emotions or [],
            relations=client.relations or [],
            work=client.work or [],
            life=client.life or [],
            personal=client.personal or [],
            format=client.format or [],
        )
