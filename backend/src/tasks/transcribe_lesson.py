import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from src.config import settings
from src.crud import Store
from src.services.transcription import pipeline
from src.services.transcription.guarded import transcribe_guarded
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _process(session_maker: sessionmaker, transcript_id: UUID) -> None:
    # Статус PROCESSING коммитим сразу, чтобы клиент видел прогресс,
    # а распознавание (минуты) не держало открытую транзакцию.
    async with session_maker() as session:
        store = Store(session=session)
        job = await pipeline.start_processing(store, transcript_id)
        await session.commit()
    if job is None:
        return

    try:
        # Распознавание синхронное и тяжёлое - уводим из event loop. Внутри результат
        # проверяется на зацикливание модели, при необходимости запускается запасной вариант.
        guarded = await asyncio.to_thread(
            transcribe_guarded,
            job.audio_path,
            settings.TRANSCRIBE_LANGUAGE,
            job.prompt,
            job.model,
        )
    except Exception as exc:
        # В базу уходит только текст ошибки, а traceback нужен в логе воркера.
        logger.exception("Транскрибация %s не удалась", transcript_id)
        async with session_maker() as session:
            await pipeline.save_failure(Store(session=session), transcript_id, str(exc))
            await session.commit()
        return

    async with session_maker() as session:
        await pipeline.save_result(
            Store(session=session), transcript_id, guarded.result, note=guarded.note
        )
        await session.commit()


async def _run(transcript_id: UUID) -> None:
    # Celery вызывает asyncio.run() на каждую задачу, то есть у каждой задачи свой
    # event loop. Общий пул соединений из core/db/database.py привязывается к loop
    # первой задачи и на второй падает с "attached to a different loop", поэтому здесь
    # отдельный движок без пула, который закрывается вместе с задачей.
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_maker = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    try:
        await _process(session_maker, transcript_id)
    finally:
        await engine.dispose()


@celery_app.task(name="tasks.transcribe_lesson")
def transcribe_lesson_task(transcript_id: str) -> None:
    """Celery-обёртка: распознаёт запись урока и сохраняет сегменты."""
    asyncio.run(_run(UUID(transcript_id)))
