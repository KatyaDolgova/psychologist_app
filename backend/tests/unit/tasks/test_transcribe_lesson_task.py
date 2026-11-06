import asyncio
import uuid

import pytest
from sqlalchemy.pool import NullPool

from src.tasks import transcribe_lesson as task_module


class FakeEngine:
    def __init__(self):
        self.disposed = False

    async def dispose(self):
        self.disposed = True


@pytest.fixture
def engines(monkeypatch):
    """Подменяем создание движка и саму обработку, чтобы проверить только обвязку."""
    created: list[tuple[FakeEngine, dict]] = []

    def fake_create_async_engine(url, **kwargs):
        engine = FakeEngine()
        created.append((engine, kwargs))
        return engine

    async def fake_process(session_maker, transcript_id):
        return None

    monkeypatch.setattr(task_module, "create_async_engine", fake_create_async_engine)
    monkeypatch.setattr(task_module, "_process", fake_process)
    return created


def test_each_task_gets_its_own_engine_without_a_pool(engines):
    # Celery запускает каждую задачу в новом event loop (asyncio.run). Общий пул
    # соединений привязывается к loop первой задачи и ломает вторую
    # ("attached to a different loop"), поэтому пул в воркере недопустим.
    asyncio.run(task_module._run(uuid.uuid4()))
    asyncio.run(task_module._run(uuid.uuid4()))

    assert len(engines) == 2
    assert engines[0][0] is not engines[1][0]
    assert all(kwargs["poolclass"] is NullPool for _, kwargs in engines)


def test_engine_is_disposed_after_the_task(engines):
    asyncio.run(task_module._run(uuid.uuid4()))

    assert engines[0][0].disposed


def test_engine_is_disposed_even_if_processing_fails(engines, monkeypatch):
    async def failing_process(session_maker, transcript_id):
        raise RuntimeError("сбой")

    monkeypatch.setattr(task_module, "_process", failing_process)

    with pytest.raises(RuntimeError, match="сбой"):
        asyncio.run(task_module._run(uuid.uuid4()))

    assert engines[0][0].disposed
