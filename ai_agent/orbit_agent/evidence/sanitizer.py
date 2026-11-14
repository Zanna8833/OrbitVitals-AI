"""Screening of untrusted text before it is shown to a language model.

Retrieved passages and free-text fields returned by the backend are data. A passage
that addresses the reader with instructions is not evidence, so it is quarantined and
never reaches the model. This screen is one layer of several: the prompt marks all
supplied text as data, the model has no tools, it can only refer to facts and passages by
identifier, and every sentence it writes is verified afterwards
(`orbit_agent.verifier`). A pattern list cannot recognise every attack, which is why the
later layers do not rely on it.
"""

from __future__ import annotations

import re

_RULES: dict[str, re.Pattern[str]] = {
    "override_previous_instructions": re.compile(
        r"\b(ignore|disregard|forget|override)\b.{0,40}\b(instruction|prompt|rule|guideline|"
        r"context|above|previous|prior)",
        re.IGNORECASE | re.DOTALL,
    ),
    "new_instructions": re.compile(
        r"\b(new|updated|revised|real|actual)\s+(instruction|directive|system prompt|task)s?\b",
        re.IGNORECASE,
    ),
    "role_reassignment": re.compile(
        r"\b(you are now|act as|pretend to be|from now on you|you must now)\b", re.IGNORECASE
    ),
    "addresses_the_model": re.compile(
        r"\b(as an ai|ai assistant|language model|system prompt|the assistant (must|should|"
        r"will)|dear (assistant|model))\b",
        re.IGNORECASE,
    ),
    "chat_role_marker": re.compile(
        r"(^|\n)\s*(system|assistant|user|developer)\s*:|<\|[^|>]{1,40}\|>|\[/?INST\]|"
        r"</?(system|assistant|instructions?)>|###\s*(system|instruction)",
        re.IGNORECASE,
    ),
    "output_directive": re.compile(
        r"\b(respond|reply|answer|output|print|say|write|state|report)\b.{0,30}\b(only|exactly|"
        r"the following|verbatim|that the (crew|astronaut|patient))",
        re.IGNORECASE | re.DOTALL,
    ),
    "secrecy_directive": re.compile(
        r"\bdo not (tell|mention|reveal|disclose|cite)\b|\bwithout (telling|mentioning)\b",
        re.IGNORECASE,
    ),
}


def screen_text(text: str) -> list[str]:
    """Return the names of the instruction-like patterns found in `text`."""
    return [name for name, pattern in _RULES.items() if pattern.search(text)]
