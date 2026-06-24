"""Output validators for all skills: numeric guard, word cap, section checks, secret scan."""
from __future__ import annotations

import re
from typing import Optional

from ..security.scanner import scan_text


class SkillValidationError(Exception):
    pass


def extract_numbers(text: str) -> set[str]:
    """Extract all numbers and date-like strings from text."""
    nums = set(re.findall(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b", text))
    dates = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}\b", text))
    # Also grab percentages
    pcts = set(re.findall(r"\b\d+(?:\.\d+)?%", text))
    return nums | dates | pcts


def numeric_guard(output: str, allowed_context: str) -> Optional[str]:
    """
    Return an error message if a number in output is not present in allowed_context.
    Returns None if output is clean.
    """
    output_nums = extract_numbers(output)
    allowed_nums = extract_numbers(allowed_context)
    unknown = output_nums - allowed_nums
    # Filter out trivially common numbers (0, 1, 2, 3, 100) that are likely benign
    trivial = {"0", "1", "2", "3", "100", "5", "10", "0%", "100%"}
    suspicious = unknown - trivial
    if suspicious:
        return (
            f"Numeric guard: output contains numbers not present in supplied context: "
            f"{sorted(suspicious)}. Rejecting output."
        )
    return None


def word_count_check(text: str, max_words: int) -> Optional[str]:
    words = len(text.split())
    if words > max_words:
        return f"Word count {words} exceeds limit {max_words}."
    return None


def section_check(text: str, required_sections: list[str]) -> Optional[str]:
    missing = [s for s in required_sections if s.lower() not in text.lower()]
    if missing:
        return f"Missing required sections: {missing}"
    return None


def secret_check(text: str) -> Optional[str]:
    try:
        scan_text(text, label="skill output")
        return None
    except Exception as e:
        return str(e)


def validate_slack_output(
    text: str,
    allowed_context: str,
    max_words: int = 180,
) -> list[str]:
    """Run all validators on a Slack status output. Returns list of errors (empty = clean)."""
    errors: list[str] = []
    if e := word_count_check(text, max_words):
        errors.append(e)
    if e := numeric_guard(text, allowed_context):
        errors.append(e)
    if e := section_check(text, ["Status:"]):
        errors.append(e)
    if e := secret_check(text):
        errors.append(e)
    return errors
