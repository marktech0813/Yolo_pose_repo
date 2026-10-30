from app.asr.transcriber import WordTiming
from app.pronunciation.alerts import find_pronunciation_alerts


def test_flags_low_confidence_content_word():
    words = [
        WordTiming("The", 0.0, 0.1, 0.9),
        WordTiming("beautiful", 0.1, 0.5, 0.2),
        WordTiming("day", 0.5, 0.7, 0.95),
    ]
    alerts = find_pronunciation_alerts(words)
    assert len(alerts) == 1
    assert "beautiful" in alerts[0].word.lower()


def test_skips_function_and_short_and_filler():
    words = [
        WordTiming("the", 0.0, 0.1, 0.1),
        WordTiming("um", 0.1, 0.2, 0.1),
        WordTiming("to", 0.2, 0.3, 0.1),
        WordTiming("hi", 0.3, 0.4, 0.1),
    ]
    assert find_pronunciation_alerts(words) == []
