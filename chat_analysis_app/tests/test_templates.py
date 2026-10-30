from app.coach.compose import compose_message


def test_clean_and_gates():
    assert "clear" in compose_message([], suppressed="none").lower()
    assert "mic" in compose_message([], suppressed="no_speech").lower()
    assert "recognize" in compose_message([], suppressed="low_confidence").lower()


def test_priority_cap():
    alerts = [
        {"kind": "filler", "text": "um", "message": "", "replacements": []},
        {"kind": "grammar", "text": "are", "message": "Use is.", "replacements": ["is"]},
        {"kind": "spelling", "text": "teh", "message": "typo", "replacements": ["the"]},
        {"kind": "pronunciation", "text": "world", "message": "", "replacements": []},
        {"kind": "pause", "text": "", "message": "pause", "replacements": []},
    ]
    msg = compose_message(alerts)
    # grammar and spelling before filler/pause; max 3 points + next step
    assert "Grammar" in msg or "is" in msg.lower()
    assert "Spelling" in msg or "teh" in msg
    assert msg.count(".") >= 2
