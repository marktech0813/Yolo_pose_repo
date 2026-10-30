"""Local LanguageTool grammar and spelling checks."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app import config

logger = logging.getLogger(__name__)


@dataclass
class GrammarMatch:
    offset: int
    length: int
    message: str
    replacements: list[str]
    rule_id: str
    category: str
    kind: str  # grammar | spelling
    text: str = ""


@dataclass
class GrammarResult:
    matches: list[GrammarMatch] = field(default_factory=list)


def _category_of(match: Any) -> str:
    cat = getattr(match, "category", None)
    if cat is None and hasattr(match, "ruleIssueType"):
        return str(match.ruleIssueType or "").upper()
    if hasattr(cat, "name"):
        return str(cat.name or "").upper()
    return str(cat or "").upper()


def _rule_id_of(match: Any) -> str:
    rule = getattr(match, "ruleId", None) or getattr(match, "rule_id", None)
    if rule is None and hasattr(match, "rule"):
        rule = getattr(match.rule, "id", None)
    return str(rule or "")


def _kind_for(category: str, rule_id: str) -> str | None:
    upper_cat = category.upper()
    upper_rule = rule_id.upper()
    if "WHITESPACE" in upper_cat or "TYPOGRAPHY" in upper_cat:
        return None
    if upper_cat in config.LT_DROP_CATEGORIES and upper_cat not in config.LT_KEEP_CATEGORIES:
        return None
    if upper_cat in {"TYPOS", "MISSPelling"} or "SPELL" in upper_rule or "MORFOLOGIK" in upper_rule:
        return "spelling"
    if upper_cat in {"GRAMMAR", "CASING"} or upper_cat in config.LT_KEEP_CATEGORIES:
        return "grammar"
    # Keep unknown grammar-ish issues that look like typos
    if "TYPO" in upper_rule:
        return "spelling"
    if upper_cat in config.LT_KEEP_CATEGORIES:
        return "grammar"
    return None


def map_matches(text: str, raw_matches: list[Any]) -> list[GrammarMatch]:
    """Map LanguageTool (or fake) matches into filtered GrammarMatch list."""
    out: list[GrammarMatch] = []
    for m in raw_matches:
        offset = int(getattr(m, "offset", 0) or 0)
        length = int(getattr(m, "errorLength", None) or getattr(m, "error_length", None) or 0)
        if length <= 0:
            continue
        category = _category_of(m)
        rule_id = _rule_id_of(m)
        kind = _kind_for(category, rule_id)
        if kind is None:
            continue
        message = str(getattr(m, "message", "") or "")
        reps = list(getattr(m, "replacements", None) or [])[:3]
        replacements = [str(r) for r in reps if r]
        span = text[offset : offset + length]
        if not span.strip():
            continue
        out.append(
            GrammarMatch(
                offset=offset,
                length=length,
                message=message,
                replacements=replacements,
                rule_id=rule_id,
                category=category,
                kind=kind,
                text=span,
            )
        )
    return out


class GrammarChecker:
    def __init__(self) -> None:
        self._tool: Any = None

    @property
    def ready(self) -> bool:
        return self._tool is not None

    def load(self) -> None:
        import os

        import language_tool_python

        config.LANGUAGETOOL_DIR.mkdir(parents=True, exist_ok=True)
        os.environ["LTP_PATH"] = str(config.LANGUAGETOOL_DIR)
        logger.info("Starting local LanguageTool (%s) path=%s", config.LT_LANGUAGE, config.LANGUAGETOOL_DIR)
        self._tool = language_tool_python.LanguageTool(config.LT_LANGUAGE)
        logger.info("LanguageTool ready")

    def check(self, text: str) -> GrammarResult:
        if self._tool is None:
            raise RuntimeError("LanguageTool not loaded")
        cleaned = text.strip()
        if not cleaned:
            return GrammarResult()
        raw = self._tool.check(cleaned)
        return GrammarResult(matches=map_matches(cleaned, list(raw)))

    def close(self) -> None:
        if self._tool is not None:
            try:
                self._tool.close()
            except Exception:  # noqa: BLE001
                logger.exception("Error closing LanguageTool")
            self._tool = None


def spans_overlap(a_start: int, a_len: int, b_start: int, b_len: int) -> bool:
    a_end = a_start + a_len
    b_end = b_start + b_len
    return a_start < b_end and b_start < a_end


def char_span_for_word(text: str, word: str, occurrence: int = 0) -> tuple[int, int] | None:
    """Find the Nth case-insensitive whole-ish occurrence of word in text."""
    pattern = re.compile(re.escape(word.strip()), re.IGNORECASE)
    matches = list(pattern.finditer(text))
    if occurrence >= len(matches):
        return None
    m = matches[occurrence]
    return m.start(), m.end() - m.start()


grammar_checker = GrammarChecker()
