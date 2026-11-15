"""The language the assistant replies in: English by default, Italian when asked for.

Italian is chosen when the request sets `language: "it"`, when the operator asks for it
("in Italian", "rispondi in italiano"), or, unless detection is switched off in the
settings, when the operator writes in Italian. A message too short to tell (for example
"Crew A?") keeps the language of the previous operator message. Anything else is answered
in English. The decision is a count of frequent words of each language, a fixed rule with
no model; the word lists are engineering choices with no external source.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Literal

from orbit_agent.lexicon import italian_words

Language = Literal["en", "it"]

LANGUAGE_NAMES: dict[Language, str] = {"en": "English", "it": "Italian"}

_ENGLISH_MARKERS = re.compile(
    r"\b(the|is|are|was|were|what|why|how|who|which|when|where|does|do|did|can|could|would|"
    r"you|your|my|i|me|hello|hi|hey|thanks|thank|please|of|to|and|it|this|that|has|have|"
    r"slept|sleep|good|morning)\b",
    re.IGNORECASE,
)
_ITALIAN_MARKERS = italian_words("language_markers")
_ASKS_FOR_ENGLISH = re.compile(
    r"\b((answer|reply|respond|write|speak)\w* )?in english( again)?(,? please)?\b",
    re.IGNORECASE,
)
_ASKS_FOR_ITALIAN = re.compile(
    r"\b((answer|reply|respond|write|speak)\w* )?in italian( again)?(,? please)?\b",
    re.IGNORECASE,
)
_ITALIAN_ASKS_FOR_ITALIAN = italian_words("explicit_language")


def without_language_request(text: str | None) -> str | None:
    """The message without an explicit request for a language, for routing.

    "Rispondi in italiano: e ieri?" is routed as "e ieri?". A message that is only a
    language request is returned unchanged.
    """
    if not text:
        return text
    stripped = text
    for pattern in (_ASKS_FOR_ITALIAN, _ITALIAN_ASKS_FOR_ITALIAN, _ASKS_FOR_ENGLISH):
        stripped = pattern.sub(" ", stripped)
    stripped = re.sub(r"\s*[:;]\s*", " ", stripped)
    stripped = re.sub(r"^[\s,.!-]+|\s+(?=[,?!.])", "", stripped)
    stripped = re.sub(r"\s{2,}", " ", stripped).strip()
    return stripped if re.search(r"\w", stripped) else text


def _counts(text: str) -> tuple[int, int]:
    return len(_ITALIAN_MARKERS.findall(text)), len(_ENGLISH_MARKERS.findall(text))


def detect_language(text: str | None) -> Language:
    """Italian when the text has more Italian than English marker words; else English."""
    if not text or not text.strip():
        return "en"
    italian, english = _counts(text)
    return "it" if italian > english else "en"


def requested_language(text: str | None) -> Language | None:
    """The language the operator explicitly asks for in the message, if any."""
    if not text:
        return None
    if _ASKS_FOR_ITALIAN.search(text) or _ITALIAN_ASKS_FOR_ITALIAN.search(text):
        return "it"
    if _ASKS_FOR_ENGLISH.search(text):
        return "en"
    return None


def reply_language(
    question: str | None,
    earlier_questions: Sequence[str] = (),
    requested: Language | None = None,
    *,
    detect: bool = True,
) -> Language:
    """Language of the reply. `earlier_questions` are earlier operator messages, oldest first."""
    if requested:
        return requested
    asked = requested_language(question)
    if asked:
        return asked
    if detect and question and any(_counts(question)):
        return detect_language(question)
    for text in reversed(earlier_questions):
        asked = requested_language(text)
        if asked:
            return asked
        if detect and any(_counts(text)):
            return detect_language(text)
    return "en"
