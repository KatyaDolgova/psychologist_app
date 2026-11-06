import re
from dataclasses import dataclass

# Лектор диктует, повторяя фразу 2-3 раза подряд: это нормально. Зацикливание модели
# даёт десятки повторов, поэтому порог выбран выше обычной диктовки (проверено на
# расшифровках лекции, см. docs/TRANSCRIPTION.md).
REPEAT_THRESHOLD = 5
MAX_PHRASE_WORDS = 8

_WORD = re.compile(r"[а-яa-z0-9]+")


@dataclass(frozen=True)
class LoopFinding:
    """Фраза, которая повторяется подряд подозрительно много раз."""

    phrase: str
    repeats: int


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower().replace("ё", "е"))


def find_loop(texts: list[str]) -> LoopFinding | None:
    """Ищет в тексте зацикливание: одно слово или короткую фразу (до 8 слов),
    повторённую подряд не меньше REPEAT_THRESHOLD раз.

    Тексты склеиваются, потому что петля может пересекать границу сегментов.
    Возвращает самое длинное повторение или None.
    """
    words = _words(" ".join(texts))
    best: LoopFinding | None = None

    for size in range(1, MAX_PHRASE_WORDS + 1):
        i = 0
        while i + size * REPEAT_THRESHOLD <= len(words):
            phrase = words[i : i + size]
            repeats = 1
            while words[i + repeats * size : i + (repeats + 1) * size] == phrase:
                repeats += 1
            if repeats >= REPEAT_THRESHOLD:
                if best is None or repeats > best.repeats:
                    best = LoopFinding(phrase=" ".join(phrase), repeats=repeats)
                i += repeats * size
            else:
                i += 1
    return best
