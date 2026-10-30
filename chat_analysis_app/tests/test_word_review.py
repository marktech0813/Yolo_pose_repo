from app.analysis.word_review import build_word_reviews
from app.api.schemas import Alert


def test_marks_correct_and_issues():
    text = "This are a mistke."
    alerts = [
        Alert(kind="grammar", message="Use is", char_start=5, char_length=3, text="are", replacements=["is"]),
        Alert(kind="spelling", message="typo", char_start=11, char_length=6, text="mistke", replacements=["mistake"]),
    ]
    reviews = build_word_reviews(text, alerts)
    by_text = {r.text: r.status for r in reviews if r.text.isalpha() or r.text in {"mistke", "are", "This"}}
    assert by_text.get("This") == "correct"
    assert by_text.get("are") == "grammar"
    assert by_text.get("mistke") == "spelling"
