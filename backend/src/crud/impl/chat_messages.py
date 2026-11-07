from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import case, func, select, update

from src.crud.impl.base import BaseDAO
from src.models import ChatMessage, ClientProfile, SpecialistProfile


class ChatMessagesDAO(BaseDAO):
    """
    DAO для работы с сообщениями чатами
    """

    model = ChatMessage

    async def mark_as_read(self, chat_id: UUID, before_message_id: UUID) -> None:
        last_dt_subq = (
            select(ChatMessage.created_at)
            .where(
                ChatMessage.id == before_message_id,
                ChatMessage.chat_id == chat_id,
            )
            .scalar_subquery()
        )

        query = (
            update(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .where(ChatMessage.created_at <= last_dt_subq)
            .values(read_at=datetime.now(timezone.utc))
        )

        await self.session.execute(query)

    async def get_history(
        self,
        chat_id: UUID,
        before_message_id: UUID | None = None,
        limit: int = 50,
    ) -> list:
        cp = ClientProfile.__table__.alias("cp")
        sp = SpecialistProfile.__table__.alias("sp")

        conditions = [ChatMessage.chat_id == chat_id]

        if before_message_id is not None:
            cursor_dt = (
                select(ChatMessage.created_at)
                .where(
                    ChatMessage.id == before_message_id, ChatMessage.chat_id == chat_id
                )
                .scalar_subquery()
            )
            conditions.append(ChatMessage.created_at < cursor_dt)

        stmt = (
            select(
                ChatMessage.id,
                ChatMessage.chat_id,
                ChatMessage.author_id,
                ChatMessage.text,
                ChatMessage.media_url,
                ChatMessage.created_at,
                ChatMessage.read_at,
                ChatMessage.reply_to,
                ChatMessage.updated_at,
                case(
                    (cp.c.id.is_not(None), cp.c.name),
                    else_=func.concat(sp.c.first_name, " ", sp.c.last_name),
                ).label("author_name"),
                func.coalesce(cp.c.avatar, sp.c.avatar).label("author_avatar"),
                case(
                    (cp.c.id.is_not(None), "CLIENT"),
                    else_="SPECIALIST",
                ).label("author_role"),
            )
            .outerjoin(cp, cp.c.id == ChatMessage.author_id)
            .outerjoin(sp, sp.c.id == ChatMessage.author_id)
            .where(*conditions)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        rows = result.mappings().all()
        return list(reversed(rows))
