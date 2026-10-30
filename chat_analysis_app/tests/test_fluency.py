from app.asr.transcriber import WordTiming
from app.fluency.fillers import find_fillers_in_text, find_fillers_in_words
from app.fluency.metrics import compute_fluency


def test_fillers_in_text():
    hits = find_fillers_in_text("Um, I mean, that was fine.")
    texts = {h.text for h in hits}
    assert "um" in texts
    assert "i mean" in texts


def test_fillers_in_words():
    words = [
        WordTiming("Um", 0.0, 0.2, 0.9),
        WordTiming("you", 0.2, 0.3, 0.9),
        WordTiming("know", 0.3, 0.5, 0.9),
        WordTiming("yes", 0.5, 0.7, 0.9),
    ]
    hits = find_fillers_in_words(words)
    assert any(h.text == "um" for h in hits)
    assert any(h.text == "you know" for h in hits)


def test_pause_and_repeat_and_wpm():
    words = [
        WordTiming("hello", 0.0, 0.3, 0.9),
        WordTiming("hello", 0.3, 0.6, 0.9),
        WordTiming("there", 2.0, 2.3, 0.9),
        WordTiming("friend", 2.3, 2.6, 0.9),
        WordTiming("today", 2.6, 3.0, 0.9),
        WordTiming("again", 3.0, 3.4, 0.9),
        WordTiming("please", 3.4, 3.8, 0.9),
        WordTiming("listen", 3.8, 4.2, 0.9),
        WordTiming("closely", 4.2, 4.8, 0.9),
        WordTiming("now", 4.8, 5.2, 0.9),
        WordTiming("okay", 5.2, 5.6, 0.9),
    ]
    m = compute_fluency(words)
    assert m.pauses
    assert m.pauses[0].duration >= 0.8
    assert m.repeats
    assert m.repeats[0].word.lower().startswith("hello")
    assert m.wpm is not None
