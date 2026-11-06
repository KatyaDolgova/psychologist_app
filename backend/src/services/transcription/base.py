from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(frozen=True)
class Segment:
    """Реплика в транскрипте - общий формат для любого источника аудио."""

    start: float
    end: float
    text: str
    speaker: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TranscriptionResult:
    language: str
    segments: list[Segment]


class Transcriber(Protocol):
    """Движок распознавания речи.

    Синхронный: вызывается из Celery-воркера (в API-процессе модель не грузится).
    Реализации взаимозаменяемы - локальная модель или облачное API.
    """

    def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
        prompt: str | None = None,
    ) -> TranscriptionResult:
        """prompt — тема или ключевые слова: помогает писать термины верно."""
        ...
