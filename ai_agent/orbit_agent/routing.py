"""Explicit routing: what kind of answer Qwen writes, and whether MedGemma reviews it.

Every decision here is a fixed rule over the question text and the verified results, so
it is reproducible and can be audited from the response (`generation.question_kind`,
`generation.answer_profile`, `generation.specialist.decision`). No model takes part in
routing.

Question kinds, checked in this order:

- `clinical_advice`: asks for a diagnosis or treatment. Full answer, no advice given.
- `greeting`: conversation. Greetings, thanks, questions about the assistant or about
  OrbitVitals ("hello", "what can you do?", "how does OrbitVitals work?"), and any message
  with no subject the assistant can answer from (no crew member, no health or data topic,
  no space science): small talk, requests outside OrbitVitals, or a bare "why?" that would
  need an earlier exchange the API does not keep. Short conversational answer, no report,
  no evidence retrieval.
- `general`: science, the dashboard or the mission, without reference to this crew
  member's data. Evidence-led answer.
- `factual`: asks for stored values. Brief answer.
- `interpretive` (or `none` without a question): full explanation of the results.

MedGemma is never consulted for conversation, general questions, factual questions or
requests for advice; for the others only when a verified reading interprets a flagged
result. Questions are recognised in English and Italian; the Italian words are in
`orbit_agent/lexicon/italian.json`. The keyword lists are engineering choices with no
external source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from orbit_agent.lexicon import italian_words
from orbit_agent.models import Fact, Interpretation, SpecialistDecision

QuestionKind = Literal["none", "greeting", "general", "factual", "interpretive", "clinical_advice"]
AnswerProfile = Literal["conversation", "general", "brief", "full"]

# A question asking for a value, a date or a count.
_FACTUAL_START = re.compile(
    r"^\s*(what|which|when|how (many|much|long)|list|show|give|tell me)\b", re.IGNORECASE
)
# Words that ask for meaning, cause, comparison or judgement: never a simple lookup.
_INTERPRETIVE = re.compile(
    r"\b(why|mean\w*|explain\w*|interpret\w*|concern\w*|worr\w*|normal|abnormal|health\w*|"
    r"risk\w*|cause\w*|compare\w*|comparison|trend\w*|declin\w*|improv\w*|worse\w*|serious|"
    r"should|okay|ok|fine|wrong|safe\w*|problem\w*|physiolog\w*|clinical\w*|significan\w*|"
    r"trust\w*|reliab\w*|affect\w*|effect\w*|impact\w*|"
    # Questions about research context are not lookups of stored values either.
    r"nasa|research\w*|stud(y|ies)|evidence|literature|dataset\w*)\b",
    re.IGNORECASE,
)
# Requests for diagnosis or treatment. The agent never provides them; a second model
# cannot add anything the verifier would let through, so it is not consulted.
_CLINICAL_ADVICE = re.compile(
    r"\b(diagnos\w*|medication\w*|medicine\w*|drug\w*|dose\w*|dosage|pill\w*|prescri\w*|"
    r"treat\w*|therap\w*|cure\w*|melatonin|supplement\w*|disease\w*|disorder\w*|"
    r"insomnia|apnea|depress\w*)\b",
    re.IGNORECASE,
)
# Greetings, thanks and acknowledgements, at the start of the message.
_GREETING = re.compile(
    r"^\s*(hi|hello|hey|hiya|good (morning|afternoon|evening)|thanks|thank you|cheers|"
    r"ok|okay|got it|great|perfect|bye|goodbye|see you)\b",
    re.IGNORECASE,
)
_ABOUT_THE_ASSISTANT = re.compile(
    r"^\s*(who are you|what are you|what can you do|how can you help|how are you|help)\b",
    re.IGNORECASE,
)
_ABOUT_THE_PLATFORM = re.compile(
    r"\b(how does (orbitvitals|this|it|the (app|platform|system|assistant|tool)) work|"
    r"what is orbitvitals|what does orbitvitals do|how do i use (it|this|orbitvitals))\b",
    re.IGNORECASE,
)
# Something the assistant can answer from: a crew member, a health or data topic. Space
# science and the dashboard are recognised by _GENERAL_CUE, which is checked first.
_SUBJECT_CUE = re.compile(
    r"\b(crew|astronaut\w*|noor|chen|vega|sim-mission-\S+|sleep\w*|slept|nap\w*|rest|bed|"
    r"activit\w*|active|exercis\w*|workout\w*|training|steps?|energy|calorie\w*|heart|pulse|"
    r"vital\w*|blood|oxygen|temperature|nutrition|food|diet|hydrat\w*|weight|health\w*|"
    r"body|muscle\w*|bone\w*|data|results?|status\w*|trend\w*|baselines?|measure\w*|"
    r"metric\w*|records?|recorded|readings?|values?|flag\w*|sensor\w*|device\w*|"
    r"physiolog\w*|clinical\w*|risk\w*|declin\w*|improv\w*|worse\w*|nights?|missing|gaps?|"
    r"radiation|cosmic|circadian|light\w*|noise|fatigue|tired\w*|stress\w*|cognit\w*|"
    r"vision|cardio\w*|isolation|workload|schedule\w*|"
    r"everything (ok|okay|fine|alright)|anything wrong)\b",
    re.IGNORECASE,
)
_ITALIAN = {
    key: italian_words(key, anchored=key in {"greeting", "about_assistant", "factual_start"})
    for key in (
        "greeting",
        "about_assistant",
        "about_platform",
        "general_cue",
        "dashboard",
        "crew_cue",
        "subject_cue",
        "factual_start",
        "interpretive",
        "clinical_advice",
        "earlier_exchange",
        "mission",
    )
}


def _matches(english: re.Pattern[str], italian_key: str, text: str) -> bool:
    return bool(english.search(text) or _ITALIAN[italian_key].search(text))


def _greeting_only(text: str) -> bool:
    """A greeting or an acknowledgement followed by at most two words ("hi there")."""
    match = _GREETING.match(text) or _ITALIAN["greeting"].match(text)
    return bool(match) and len(re.findall(r"\w+", text[match.end() :])) <= 2


# Words that make a question general: science, the dashboard, the mission.
_GENERAL_CUE = re.compile(
    r"\b(in space|spaceflight|space ?flight|astronauts?|microgravity|weightless\w*|"
    r"in general|generally|dashboard|this screen|the app|mission|status(es)? mean\w*|"
    r"what does (an? |the )?['\"]?(attention|nominal|insufficient[_ ]data)|nasa|"
    r"research\w*|stud(y|ies)|literature|bed ?rest)\b",
    re.IGNORECASE,
)
# Words that tie a question to this crew member's stored data.
_CREW_CUE = re.compile(
    r"\b(crew member|this crew|crew [abc]|sim-mission-\S+|noor|chen|vega|his|her|hers|their|"
    r"my|mine|latest|last night|recorded|records?|measurements?|readings?|baselines?|"
    r"values?|flagged|today|yesterday)\b",
    re.IGNORECASE,
)
# A question that refers to an earlier exchange. The API answers one request at a time.
_EARLIER_EXCHANGE = re.compile(
    r"\b(earlier|before|previous(ly)?|last time|again|you (said|told|mentioned)|"
    r"as (i|we) (said|asked|discussed)|remember)\b",
    re.IGNORECASE,
)
_FLAGGED = {"attention", "alert"}


def classify_question(question: str | None) -> QuestionKind:
    """Classify the operator question for routing. No question means a full explanation."""
    if not question or not question.strip():
        return "none"
    if _matches(_CLINICAL_ADVICE, "clinical_advice", question):
        return "clinical_advice"
    words = len(re.findall(r"\w+", question))
    if _matches(_ABOUT_THE_ASSISTANT, "about_assistant", question) and words <= 8:
        return "greeting"
    if _greeting_only(question):
        return "greeting"
    crew = _matches(_CREW_CUE, "crew_cue", question)
    if _matches(_ABOUT_THE_PLATFORM, "about_platform", question) and words <= 10 and not crew:
        return "greeting"
    if _matches(_GENERAL_CUE, "general_cue", question) and not crew:
        return "general"
    if not _matches(_SUBJECT_CUE, "subject_cue", question):
        # Nothing the stored records or the evidence could answer: reply in conversation
        # instead of producing an unrequested report.
        return "greeting"
    asks_for_values = bool(
        _FACTUAL_START.search(question) or _ITALIAN["factual_start"].search(question)
    )
    if asks_for_values and not _matches(_INTERPRETIVE, "interpretive", question):
        return "factual"
    return "interpretive"


ConversationIntent = Literal["greeting", "about", "earlier_exchange", "out_of_scope"]


def _asks_about_the_assistant(question: str) -> bool:
    words = len(re.findall(r"\w+", question))
    return bool(
        (_matches(_ABOUT_THE_ASSISTANT, "about_assistant", question) and words <= 8)
        or (_matches(_ABOUT_THE_PLATFORM, "about_platform", question) and words <= 10)
    )


def is_conversational(question: str | None) -> bool:
    """A greeting, thanks, acknowledgement or question about the assistant itself."""
    return bool(question) and (_greeting_only(question) or _asks_about_the_assistant(question))


def conversation_intent(question: str | None) -> ConversationIntent:
    """What a conversational message asks for, so Qwen gets one short instruction."""
    if not question:
        return "greeting"
    if _asks_about_the_assistant(question):
        return "about"
    if _greeting_only(question):
        return "greeting"
    if refers_to_earlier_exchange(question):
        return "earlier_exchange"
    return "out_of_scope"


def refers_to_earlier_exchange(question: str | None) -> bool:
    return bool(question and _matches(_EARLIER_EXCHANGE, "earlier_exchange", question))


def mentions_mission(question: str | None) -> bool:
    return bool(question and _matches(re.compile(r"\bmissions?\b", re.I), "mission", question))


# A question about the dashboard or what a status means. It is answered from the backend
# statuses and the fixed rules, not from the literature: in the corpus "attention" is a
# cognitive skill, so a search would return unrelated entries.
_DASHBOARD = re.compile(
    r"\b(dashboard|this screen|the app|status(es)? mean\w*|"
    r"what does (an? |the )?['\"]?(attention|nominal|alert|insufficient[_ ]data))",
    re.IGNORECASE,
)


def asks_about_the_dashboard(question: str | None) -> bool:
    return bool(question and _matches(_DASHBOARD, "dashboard", question))


def answer_profile(kind: QuestionKind) -> AnswerProfile:
    """Draft size for each question kind."""
    return {
        "greeting": "conversation",
        "general": "general",
        "factual": "brief",
    }.get(kind, "full")


@dataclass(frozen=True)
class SpecialistRoute:
    consult: bool
    decision: SpecialistDecision
    reason: str


def route_specialist(
    kind: QuestionKind, interpretations: list[Interpretation], facts: dict[str, Fact]
) -> SpecialistRoute:
    """Decide whether the biomedical specialist reviews the verified readings.

    It is consulted only when a reading interprets a flagged screening result (status
    'attention' or 'alert') and the question asks for meaning rather than a value, a
    treatment, small talk or general knowledge. Readings about data quality or
    insufficient data contain no physiological claim to review.
    """
    if kind == "greeting":
        return SpecialistRoute(
            False, "conversational_question", "The request is conversational, not biomedical."
        )
    if kind == "general":
        return SpecialistRoute(
            False,
            "general_question",
            "The question is about general knowledge, not this crew member's results.",
        )
    if kind == "factual":
        return SpecialistRoute(
            False, "factual_question", "The question asks for stored values, not their meaning."
        )
    if kind == "clinical_advice":
        return SpecialistRoute(
            False,
            "clinical_advice_question",
            "The question asks for a diagnosis or treatment, which the agent does not provide.",
        )
    signals = [item for item in interpretations if item.kind == "screening_signal"]
    if not signals:
        return SpecialistRoute(
            False,
            "no_physiological_reading",
            "The explanation contains no physiological reading to review.",
        )
    flagged = any(
        facts[fact_id].data.get("status") in _FLAGGED
        for item in signals
        for fact_id in item.fact_ids
        if fact_id in facts
    )
    if not flagged:
        return SpecialistRoute(
            False,
            "no_flagged_result",
            "No reading interprets a flagged result, so no second review is needed.",
        )
    return SpecialistRoute(True, "consulted", "A reading interprets a flagged screening result.")
