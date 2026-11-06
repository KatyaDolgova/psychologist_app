from collections.abc import Callable
from dataclasses import dataclass

from src.models.enums.transcripts import TranscriptionModel
from src.services.transcription.base import Transcriber, TranscriptionResult
from src.services.transcription.catalog import get_option
from src.services.transcription.factory import get_transcriber
from src.services.transcription.loops import LoopFinding, find_loop

PHRASE_PREVIEW_CHARS = 60


@dataclass(frozen=True)
class GuardedResult:
    result: TranscriptionResult
    # Предупреждение для пользователя; None, если всё прошло чисто.
    note: str | None
    # Какой вариант в итоге дал текст.
    used: TranscriptionModel


def _preview(finding: LoopFinding) -> str:
    phrase = finding.phrase
    if len(phrase) > PHRASE_PREVIEW_CHARS:
        phrase = phrase[:PHRASE_PREVIEW_CHARS] + "..."
    return f"«{phrase}» (повторов подряд: {finding.repeats})"


def _loop_of(result: TranscriptionResult) -> LoopFinding | None:
    return find_loop([segment.text for segment in result.segments])


def transcribe_guarded(
    audio_path: str,
    language: str | None,
    prompt: str | None,
    model: TranscriptionModel,
    transcriber_for: Callable[[TranscriptionModel], Transcriber] = get_transcriber,
) -> GuardedResult:
    """Распознаёт запись и проверяет результат на зацикливание модели.

    Whisper иногда застревает на одной фразе и выдаёт её десятки раз, теряя остаток
    записи. Если выбранный вариант зациклился, запись распознаётся запасным
    вариантом «Быстро». Результат не отбрасывается никогда: если подозрение осталось,
    текст сохраняется вместе с предупреждением (эвристика может ошибиться, а терять
    транскрипт из-за этого нельзя).
    """
    first = transcriber_for(model).transcribe(audio_path, language, prompt)
    loop = _loop_of(first)
    if loop is None:
        return GuardedResult(result=first, note=None, used=model)

    requested = get_option(model).title
    if model == TranscriptionModel.FAST:
        return GuardedResult(
            result=first,
            note=(
                f"В тексте повторяется {_preview(loop)}: возможно, распознавание "
                "зациклилось и конец записи распознан неверно."
            ),
            used=model,
        )

    fallback_title = get_option(TranscriptionModel.FAST).title
    prefix = f"Вариант «{requested}» зациклился на фразе {_preview(loop)}. "
    try:
        second = transcriber_for(TranscriptionModel.FAST).transcribe(
            audio_path, language, prompt
        )
    except Exception as exc:
        return GuardedResult(
            result=first,
            note=prefix
            + f"Запасной вариант «{fallback_title}» не удалось запустить: {exc}",
            used=model,
        )

    second_loop = _loop_of(second)
    if second_loop is None:
        return GuardedResult(
            result=second,
            note=prefix + f"Текст получен вариантом «{fallback_title}».",
            used=TranscriptionModel.FAST,
        )
    return GuardedResult(
        result=second,
        note=(
            prefix
            + f"Вариант «{fallback_title}» тоже повторяет {_preview(second_loop)}: "
            "конец записи может быть распознан неверно."
        ),
        used=TranscriptionModel.FAST,
    )
