import pytest

from src.models.enums.transcripts import TranscriptionModel
from src.services.transcription.base import Segment, TranscriptionResult
from src.services.transcription.guarded import transcribe_guarded

FAST = TranscriptionModel.FAST
QUALITY = TranscriptionModel.QUALITY

GOOD_TEXT = "Законодательная власть это сложный комплекс субъектов"
LOOP_TEXT = "Начало лекции. " + "представительство " * 30


def _result(text: str) -> TranscriptionResult:
    return TranscriptionResult(language="ru", segments=[Segment(0.0, 5.0, text)])


class FakeEngine:
    def __init__(self, text: str | None = None, error: Exception | None = None):
        self._text, self._error = text, error
        self.calls = 0

    def transcribe(self, audio_path, language=None, prompt=None):
        self.calls += 1
        if self._error:
            raise self._error
        return _result(self._text)


def _run(model, engines):
    return transcribe_guarded(
        "/media/a.ogg", "ru", None, model, transcriber_for=lambda m: engines[m]
    )


def test_clean_result_is_returned_without_fallback():
    engines = {QUALITY: FakeEngine(GOOD_TEXT), FAST: FakeEngine(GOOD_TEXT)}

    outcome = _run(QUALITY, engines)

    assert outcome.note is None
    assert outcome.used == QUALITY
    assert outcome.result.segments[0].text == GOOD_TEXT
    assert engines[FAST].calls == 0


def test_looping_variant_falls_back_to_fast():
    engines = {QUALITY: FakeEngine(LOOP_TEXT), FAST: FakeEngine(GOOD_TEXT)}

    outcome = _run(QUALITY, engines)

    assert outcome.used == FAST
    assert outcome.result.segments[0].text == GOOD_TEXT
    assert "Точнее" in outcome.note and "зациклился" in outcome.note
    assert "представительство" in outcome.note
    assert "«Быстро»" in outcome.note
    assert engines[QUALITY].calls == 1 and engines[FAST].calls == 1


def test_if_fallback_also_loops_text_is_kept_with_a_warning():
    engines = {QUALITY: FakeEngine(LOOP_TEXT), FAST: FakeEngine(LOOP_TEXT)}

    outcome = _run(QUALITY, engines)

    assert outcome.used == FAST
    assert outcome.result.segments  # транскрипт не теряется
    assert "тоже повторяет" in outcome.note


def test_fast_variant_has_no_fallback_but_gets_a_warning():
    engines = {FAST: FakeEngine(LOOP_TEXT), QUALITY: FakeEngine(GOOD_TEXT)}

    outcome = _run(FAST, engines)

    assert outcome.used == FAST
    assert outcome.result.segments[0].text == LOOP_TEXT
    assert "возможно" in outcome.note
    assert engines[QUALITY].calls == 0


def test_fallback_failure_keeps_first_result_with_a_warning():
    engines = {
        QUALITY: FakeEngine(LOOP_TEXT),
        FAST: FakeEngine(error=RuntimeError("нет памяти")),
    }

    outcome = _run(QUALITY, engines)

    assert outcome.used == QUALITY
    assert outcome.result.segments[0].text == LOOP_TEXT
    assert "не удалось запустить" in outcome.note
    assert "нет памяти" in outcome.note


def test_error_in_requested_variant_is_not_swallowed():
    engines = {QUALITY: FakeEngine(error=RuntimeError("битый файл"))}

    with pytest.raises(RuntimeError, match="битый файл"):
        _run(QUALITY, engines)


def test_long_phrase_is_shortened_in_note():
    long_phrase = " ".join(f"длиннейшееслово{i}" for i in range(8))
    engines = {
        QUALITY: FakeEngine((long_phrase + " ") * 5),
        FAST: FakeEngine(GOOD_TEXT),
    }

    outcome = _run(QUALITY, engines)

    assert "..." in outcome.note
    assert len(outcome.note) < 400
