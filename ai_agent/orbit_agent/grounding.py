"""Numeric and date grounding: which numbers may a sentence about a fact contain?

A sentence is grounded when every number and every date in it can be traced to the facts
or passages it cites. Values may be rounded, written as a percentage of a fraction, or
written in hours when the source is in minutes; nothing else is accepted. The check is
about presence, not meaning: it catches invented or miscopied values, not a correct
number used in a misleading sentence.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Any

from orbit_agent.evidence.store import Passage
from orbit_agent.models import Fact

_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_TIMESTAMP = re.compile(
    r"\b(\d{4}-\d{2}-\d{2})[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?"
)
_DATE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
# Opaque identifiers such as `sim-mission-v1-02:current:record-05` or `NASA-SLEEP-01`:
# a letter-initial token joined by `-`, `_` or `:`. Digits inside them are not values.
_IDENTIFIER = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:[-_:][A-Za-z0-9]+)+\b")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])")
_NUMBER_WORDS = {
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}
_NUMBER_WORD = re.compile(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b", re.IGNORECASE)
_TOLERANCE = 1e-6


def dates_in(text: str) -> set[str]:
    """Calendar dates written as YYYY-MM-DD, including the date part of timestamps."""
    return set(_DATE.findall(_UUID.sub(" ", text)))


def numbers_in(text: str) -> list[float]:
    """Magnitudes of the numeric values in `text`, ignoring identifiers and dates.

    Signs are dropped: prose states direction in words ("50 min below"), so only the
    magnitude can be compared.
    """
    cleaned = _UUID.sub(" ", text)
    cleaned = _TIMESTAMP.sub(" ", cleaned)
    cleaned = _DATE.sub(" ", cleaned)
    cleaned = _IDENTIFIER.sub(" ", cleaned)
    cleaned = _THOUSANDS.sub("", cleaned)
    values = [float(match) for match in _NUMBER.findall(cleaned)]
    values.extend(float(_NUMBER_WORDS[word.lower()]) for word in _NUMBER_WORD.findall(cleaned))
    return values


def _walk(value: Any, numbers: list[float], texts: list[str]) -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, int | float):
        numbers.append(abs(float(value)))
    elif isinstance(value, str):
        texts.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            _walk(item, numbers, texts)
    elif isinstance(value, list | tuple):
        # The length of a list is a count a sentence may state ("two missing nights").
        numbers.append(float(len(value)))
        for item in value:
            _walk(item, numbers, texts)


def presentations(values: Iterable[float], *, minutes: bool) -> set[float]:
    """Add the accepted presentations of each value: rounding, percent, hours."""
    expanded: set[float] = set()

    def add_rounded(value: float, max_decimals: int) -> None:
        for decimals in range(max_decimals + 1):
            scale = 10**decimals
            expanded.add(round(value, decimals))
            expanded.add(math.floor(value * scale + _TOLERANCE) / scale)

    for raw in values:
        value = abs(raw)
        add_rounded(value, 3)
        if 0 < value < 1:
            add_rounded(value * 100, 2)
        if minutes and value >= 60:
            # One hour is 60 minutes by definition.
            add_rounded(value / 60, 2)
            expanded.add(float(value % 60))
    return expanded


def _date_parts(dates: Iterable[str]) -> set[float]:
    parts: set[float] = set()
    for date in dates:
        year, month, day = date.split("-")
        parts.update((float(year), float(month), float(day)))
    return parts


def fact_dates(fact: Fact) -> set[str]:
    texts: list[str] = [fact.statement]
    _walk(fact.data, [], texts)
    found: set[str] = set()
    for text in texts:
        found |= dates_in(text)
    return found


def fact_numbers(fact: Fact) -> set[float]:
    """Every number a sentence citing `fact` may contain."""
    numbers: list[float] = []
    texts: list[str] = [fact.statement]
    _walk(fact.data, numbers, texts)
    for text in texts:
        numbers.extend(numbers_in(text))
    unit = fact.data.get("unit")
    return presentations(numbers, minutes=unit == "min") | _date_parts(fact_dates(fact))


def passage_source_text(passage: Passage) -> str:
    """Everything a sentence about a passage may draw on: its title, section and text."""
    return f"{passage.document_title}. {passage.section}. {passage.text}"


def passage_numbers(passage: Passage) -> set[float]:
    return presentations(numbers_in(passage_source_text(passage)), minutes=False)


def ungrounded_values(text: str, allowed_numbers: set[float], allowed_dates: set[str]) -> list[str]:
    """Numbers and dates in `text` that are not among the allowed values."""
    problems = [date for date in sorted(dates_in(text)) if date not in allowed_dates]
    for number in numbers_in(text):
        if not any(abs(number - allowed) <= _TOLERANCE for allowed in allowed_numbers):
            rendered = str(int(number)) if number == int(number) else str(number)
            if rendered not in problems:
                problems.append(rendered)
    return problems
