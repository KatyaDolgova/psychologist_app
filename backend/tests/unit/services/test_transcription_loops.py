from src.services.transcription.loops import (
    MAX_PHRASE_WORDS,
    REPEAT_THRESHOLD,
    find_loop,
)


def test_one_word_repeated_dozens_of_times_is_a_loop():
    text = "Итак, " + "представительство, " * 34

    finding = find_loop([text])

    assert finding.phrase == "представительство"
    assert finding.repeats == 34


def test_repeated_phrase_is_a_loop():
    finding = find_loop(["Что это такое? " * 5])

    assert finding.phrase == "что это такое"
    assert finding.repeats == 5


def test_dictation_repeated_two_or_three_times_is_not_a_loop():
    # Лектор диктует: фраза звучит 2-3 раза подряд, это нормальная речь.
    dictated = "Сложный комплекс субъектов и видов деятельности. " * 3

    assert find_loop([dictated]) is None


def test_threshold_boundary():
    below = "да " * (REPEAT_THRESHOLD - 1)
    at = "да " * REPEAT_THRESHOLD

    assert find_loop([below]) is None
    assert find_loop([at]).repeats == REPEAT_THRESHOLD


def test_case_punctuation_and_yo_are_ignored():
    assert find_loop(["Всё. всё! ВСЕ, все; всё"]).repeats == 5


def test_loop_crossing_segment_boundary_is_found():
    segments = ["слово " * 3, "слово " * 3]

    assert find_loop(segments).repeats == 6


def test_normal_text_has_no_loop():
    text = "Государство обладает суверенитетом, то есть независимостью и самостоятельностью"

    assert find_loop([text]) is None
    assert find_loop([]) is None
    assert find_loop([""]) is None


def test_long_phrase_up_to_limit_is_found_longer_is_not():
    words = [f"слово{i}" for i in range(MAX_PHRASE_WORDS)]
    too_long = [f"слово{i}" for i in range(MAX_PHRASE_WORDS + 1)]

    assert find_loop([" ".join(words)] * REPEAT_THRESHOLD).phrase == " ".join(words)
    assert find_loop([" ".join(too_long)] * REPEAT_THRESHOLD) is None


def test_the_longest_repetition_is_reported():
    text = "да да да да да " + "нет " * 9 + "потом да да да да да да"

    finding = find_loop([text])

    assert finding.phrase == "нет"
    assert finding.repeats == 9
