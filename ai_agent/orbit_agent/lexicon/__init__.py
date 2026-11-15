"""Vocabulary and fixed sentences of the languages the assistant answers in besides English.

The words are data, kept in UTF-8 JSON files next to this module, so that the source code
stays ASCII English (tests/test_architecture.py). The English patterns live in the modules
that use them; each of those modules adds the patterns of the other languages from here.
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

FOLDER = Path(__file__).parent


@cache
def italian() -> dict[str, Any]:
    """The Italian vocabulary (`italian.json`)."""
    return json.loads((FOLDER / "italian.json").read_text(encoding="utf-8"))


def italian_pattern(key: str) -> str:
    """Alternation of the Italian regular-expression fragments listed under `key`."""
    return "|".join(f"(?:{fragment})" for fragment in italian()["patterns"][key])


def italian_words(key: str, *, anchored: bool = False) -> re.Pattern[str]:
    """Compiled Italian pattern: whole words, or at the start of the text when anchored."""
    start = r"^\s*" if anchored else r"(?<!\w)"
    return re.compile(f"{start}(?:{italian_pattern(key)})(?!\\w)", re.IGNORECASE)


def italian_entry(section: str, key: str) -> str:
    """Alternation of the Italian fragments of `section[key]`, as whole words."""
    fragments = "|".join(f"(?:{fragment})" for fragment in italian()[section][key])
    return f"(?<!\\w)(?:{fragments})(?!\\w)"


def with_italian(english: re.Pattern[str], key: str) -> re.Pattern[str]:
    """`english`, extended with the Italian words listed under `patterns[key]`."""
    return re.compile(f"(?:{english.pattern})|{italian_words(key).pattern}", re.IGNORECASE)


def italian_text(key: str) -> str:
    """A fixed Italian sentence (`fixed_texts`)."""
    return italian()["fixed_texts"][key]
