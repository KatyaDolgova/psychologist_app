import asyncio
from uuid import UUID

from src.config import settings
from src.core.db.database import async_session_maker
from src.crud import Store
from src.services.transcription import pipeline
from src.services.transcription.guarded import transcribe_guarded
from src.tasks.celery_app import celery_app


async def _run(transcript_id: UUID) -> None:
    # Статус PROCESSING коммитим сразу, чтобы клиент видел прогресс,
    # а распознавание (минуты) не держало открытую транзакцию.
    async with async_session_maker() as session:
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
        async with async_session_maker() as session:
            await pipeline.save_failure(Store(session=session), transcript_id, str(exc))
            await session.commit()
        return

    async with async_session_maker() as session:
        await pipeline.save_result(
            Store(session=session), transcript_id, guarded.result, note=guarded.note
        )
        await session.commit()


@celery_app.task(name="tasks.transcribe_lesson")
def transcribe_lesson_task(transcript_id: str) -> None:
    """Celery-обёртка: распознаёт запись урока и сохраняет сегменты."""
    asyncio.run(_run(UUID(transcript_id)))
