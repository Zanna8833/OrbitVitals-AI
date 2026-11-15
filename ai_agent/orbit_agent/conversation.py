"""Multi-turn context sent by the client: which turns are used, and follow-up questions.

The agent keeps no conversation of its own. A client (the dashboard) may send the earlier
messages of a chat with each request (`ExplanationRequest.conversation`); the agent then:

- keeps the most recent turns about the requested crew member, screened for instruction-like
  text and shortened, and gives them to the model as context, never as facts;
- interprets a follow-up that has no subject of its own ("And compared to yesterday?",
  "Why?") together with the earlier operator question it continues, for routing, retrieval
  and the specialist's review query.

A message with a subject of its own (a crew member, a health or data topic) starts or
returns to a topic and is classified on its own. The word lists are engineering choices
with no external source; the Italian ones are in `orbit_agent/lexicon/italian.json`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from orbit_agent.evidence.sanitizer import screen_text
from orbit_agent.language import without_language_request
from orbit_agent.lexicon import italian_words
from orbit_agent.models import ConversationTurn, ExplanationRequest
from orbit_agent.routing import is_conversational, refers_to_earlier_exchange

# Characters of one earlier message given to the model. Enough for a question or a
# headline; an engineering choice with no external source.
MAX_TURN_CHARACTERS = 600

# Words that make a message continue the previous one.
_FOLLOW_UP_START = re.compile(
    r"^\s*(and|what about|how about|compared|versus|vs\.?|also|then|so|but|why|how come|"
    r"same|is it|was it|does it|did it|are they|were they|really|is that|does that)\b",
    re.IGNORECASE,
)
_ANAPHORA = re.compile(r"\b(it|that|this|these|those|they|them)\b", re.IGNORECASE)
# A subject of its own: a crew member, a health domain, space science or the records.
_TOPIC = re.compile(
    r"\b(crew [abc]|noor|chen|vega|sleep\w*|slept|activit\w*|exercis\w*|workout\w*|steps?|"
    r"energy|calorie\w*|heart|pulse|blood|nutrition|hydrat\w*|weight|muscle\w*|bone\w*|"
    r"radiation|microgravity|mission|sensor\w*|device\w*|records?|data)\b",
    re.IGNORECASE,
)
_ITALIAN_FOLLOW_UP_START = italian_words("follow_up_start", anchored=True)
_ITALIAN_ANAPHORA = italian_words("anaphora")
_ITALIAN_TOPIC = italian_words("topic_cue")


@dataclass(frozen=True)
class Context:
    """What the earlier turns contribute to one request."""

    turns: tuple[ConversationTurn, ...]
    question_in_context: str | None
    follow_up: bool
    # The text used for routing and retrieval: the question in context for a follow-up,
    # else the question without an explicit language request.
    routed: str | None = None

    @property
    def has_history(self) -> bool:
        return bool(self.turns)


def has_topic(text: str) -> bool:
    return bool(_TOPIC.search(text) or _ITALIAN_TOPIC.search(text))


def is_follow_up(question: str | None) -> bool:
    """A message that continues the previous question instead of naming its own subject."""
    if not question or has_topic(question) or is_conversational(question):
        return False
    if refers_to_earlier_exchange(question):
        return False  # "What did I ask before?" is about the chat, not the data
    words = len(re.findall(r"\w+", question))
    return bool(
        words <= 3
        or _FOLLOW_UP_START.search(question)
        or _ITALIAN_FOLLOW_UP_START.search(question)
        or _ANAPHORA.search(question)
        or _ITALIAN_ANAPHORA.search(question)
    )


def parse_crew_aliases(spec: str) -> dict[str, tuple[str, ...]]:
    """`"id=Name|Name;id=Name"` (settings.crew_aliases) as {crew id: names}."""
    aliases: dict[str, tuple[str, ...]] = {}
    for entry in filter(None, (part.strip() for part in spec.split(";"))):
        crew, _, names = entry.partition("=")
        aliases[crew.strip()] = tuple(n.strip() for n in names.split("|") if n.strip())
    return aliases


def other_crew_pattern(
    aliases: dict[str, tuple[str, ...]], crew_member_id: str
) -> re.Pattern[str] | None:
    """Matches a name of any crew member other than `crew_member_id`."""
    own = {name.lower() for name in aliases.get(crew_member_id, ())}
    names = sorted(
        {
            n
            for crew, ns in aliases.items()
            if crew != crew_member_id
            for n in ns
            if n.lower() not in own
        }
    )
    if not names:
        return None
    return re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b", re.IGNORECASE)


def usable_turns(
    request: ExplanationRequest,
    max_turns: int,
    aliases: dict[str, tuple[str, ...]] | None = None,
) -> tuple[ConversationTurn, ...]:
    """The most recent turns about this crew member, screened and shortened."""
    other = other_crew_pattern(aliases or {}, request.crew_member_id)
    kept: list[ConversationTurn] = []
    for turn in request.conversation[-max_turns:] if max_turns > 0 else []:
        if turn.crew_member_id and turn.crew_member_id != request.crew_member_id:
            continue  # never mix crew members
        if other and other.search(turn.text):
            continue  # a turn naming another crew member, even without crew_member_id
        if screen_text(turn.text):
            continue  # instruction-like text is not passed on
        kept.append(turn.model_copy(update={"text": turn.text[:MAX_TURN_CHARACTERS]}))
    return tuple(kept)


def build_context(
    request: ExplanationRequest,
    max_turns: int,
    aliases: dict[str, tuple[str, ...]] | None = None,
) -> Context:
    turns = usable_turns(request, max_turns, aliases)
    # "Rispondi in italiano: e ieri?" is routed as "e ieri?".
    question = without_language_request(request.question)
    alone = Context(turns=turns, question_in_context=None, follow_up=False, routed=question)
    if not turns or not is_follow_up(question):
        return alone
    # Walk back to the operator question that named the subject (at most three turns).
    chain: list[str] = []
    for turn in reversed(turns):
        if turn.role != "operator":
            continue
        chain.insert(0, without_language_request(turn.text) or turn.text)
        if has_topic(turn.text) or len(chain) == 3:
            break
    if not chain:
        return alone
    joined = " ".join([*chain, question or ""]).strip()
    return Context(turns=turns, question_in_context=joined, follow_up=True, routed=joined)
