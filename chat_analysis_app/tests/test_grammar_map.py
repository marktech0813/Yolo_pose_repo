from types import SimpleNamespace

from app.grammar.checker import map_matches


def test_map_keeps_grammar_and_typos():
    text = "This are a mistke."
    raw = [
        SimpleNamespace(
            offset=5,
            errorLength=3,
            message="Did you mean 'is'?",
            replacements=["is"],
            ruleId="AGREEMENT",
            category=SimpleNamespace(name="GRAMMAR"),
        ),
        SimpleNamespace(
            offset=11,
            errorLength=6,
            message="Possible spelling mistake",
            replacements=["mistake"],
            ruleId="MORFOLOGIK_RULE_EN_US",
            category=SimpleNamespace(name="TYPOS"),
        ),
        SimpleNamespace(
            offset=0,
            errorLength=4,
            message="style",
            replacements=[],
            ruleId="STYLE_X",
            category=SimpleNamespace(name="STYLE"),
        ),
    ]
    matches = map_matches(text, raw)
    assert len(matches) == 2
    assert matches[0].kind == "grammar"
    assert matches[0].replacements == ["is"]
    assert matches[1].kind == "spelling"
    assert matches[1].text == "mistke"
