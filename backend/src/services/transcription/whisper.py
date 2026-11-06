from src.config import settings
from src.services.transcription.base import Segment, TranscriptionResult


class FasterWhisperTranscriber:
    """Локальная транскрибация через faster-whisper.

    Пакет faster-whisper тяжёлый и ставится только в образ воркера
    (requirements-transcribe.txt), поэтому импортируется лениво.
    """

    def __init__(self, model_name: str) -> None:
        from faster_whisper import BatchedInferencePipeline, WhisperModel

        model = WhisperModel(
            model_name,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
        self._batched = settings.WHISPER_BATCHED
        # Пакетный режим обрабатывает куски записи параллельно: на CPU в 2-3 раза
        # быстрее и меньше склонен к зацикливанию на длинных записях.
        self._runner = BatchedInferencePipeline(model) if self._batched else model

    def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
        prompt: str | None = None,
    ) -> TranscriptionResult:
        options = {"language": language, "initial_prompt": prompt, "vad_filter": True}
        if self._batched:
            options["batch_size"] = settings.WHISPER_BATCH_SIZE
        segments, info = self._runner.transcribe(audio_path, **options)
        return TranscriptionResult(
            language=info.language,
            segments=[
                Segment(start=s.start, end=s.end, text=s.text.strip()) for s in segments
            ],
        )
