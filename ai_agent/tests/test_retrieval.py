"""Retrieval over the expanded corpus: relevance, diversity and unsupported questions."""

import json

import pytest

from orbit_agent.evidence.store import EvidenceStore, topics_named_in
from orbit_agent.models import ExplanationRequest
from orbit_agent.pipeline import plan_retrieval
from scripts.evaluate_retrieval import QUERIES_PATH, TOP_K, evaluate
from tests.support import CHEN, NOOR, fact_sheet, make_agent

STORE = EvidenceStore.load()
QUERIES = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))["queries"]
SUPPORTED = [item for item in QUERIES if item["category"] != "unsupported"]
UNSUPPORTED = [item for item in QUERIES if item["category"] == "unsupported"]
SLEEP_TOPICS = {"sleep", "circadian", "fatigue", "workload"}
ACTIVITY_TOPICS = {"exercise", "fitness", "muscle"}


def test_labelled_queries_refer_to_existing_entries() -> None:
    known = {passage.evidence_id for passage in STORE.passages}

    assert len(SUPPORTED) >= 40 and len(UNSUPPORTED) >= 6
    for item in SUPPORTED:
        assert item["relevant"], item["id"]
        assert set(item["relevant"]) <= known, item["id"]


def test_retrieval_quality_on_the_labelled_queries() -> None:
    """Floors set below the measured values (hit 0.96, precision 0.69, rank 0.91)."""
    report = evaluate(STORE)
    overall = report["overall"]

    assert overall["hit"] >= 0.9
    assert overall["precision"] >= 0.6
    assert overall["reciprocal_rank"] >= 0.85
    assert report["unsupported"]["correctly_empty"] == report["unsupported"]["queries"]
    for category, row in report["by_category"].items():
        assert row["hit"] >= 0.8, f"{category}: hit rate {row['hit']}"


def test_current_scoring_is_not_worse_than_the_first_version() -> None:
    current, legacy = evaluate(STORE), evaluate(STORE, legacy=True)

    assert current["overall"]["hit"] >= legacy["overall"]["hit"]
    assert current["overall"]["precision"] >= legacy["overall"]["precision"]
    assert current["unsupported"]["correctly_empty"] > legacy["unsupported"]["correctly_empty"]


@pytest.mark.parametrize("item", UNSUPPORTED, ids=lambda item: item["id"])
def test_question_outside_the_corpus_retrieves_nothing(item: dict) -> None:
    assert STORE.search(item["query"], top_k=5) == []


def test_one_shared_common_word_is_not_enough() -> None:
    # "best" occurs in one summary; the first version returned that entry for this query.
    assert STORE.search("best pizza recipe with mozzarella", legacy=True)
    assert STORE.search("best pizza recipe with mozzarella") == []
    # A query that is a single specific term still finds its entries.
    assert STORE.search("actigraphy")


@pytest.mark.parametrize("item", SUPPORTED, ids=lambda item: item["id"])
def test_results_are_spread_over_sources_and_not_repeated(item: dict) -> None:
    results = STORE.search(item["query"], top_k=5)
    urls = [result.passage.url for result in results]

    assert all(urls.count(url) <= 2 for url in urls)
    assert len({result.passage.evidence_id for result in results}) == len(results)
    assert [result.score for result in results] == sorted(
        (result.score for result in results), reverse=True
    )


def test_everyday_words_reach_the_matching_topic() -> None:
    assert topics_named_in("Why are crew members tired?") == {"fatigue"}
    assert topics_named_in("Do workouts keep the heart in shape?") == {"exercise", "cardiovascular"}
    # Words with a second meaning in this project name no topic.
    assert topics_named_in("which dose, is the data simulated, a shift, some rest") == frozenset()

    results = STORE.search("Why are crew members tired?", top_k=TOP_K)
    assert results and all("fatigue" in result.passage.topics for result in results)


def test_retrieval_is_deterministic_on_every_labelled_query() -> None:
    for item in QUERIES:
        first = STORE.search(item["query"], top_k=TOP_K)
        second = STORE.search(item["query"], top_k=TOP_K)
        assert first == second, item["id"]


# --- Retrieval inside the pipeline ---------------------------------------------------


def _retrieved(crew: str, domain: str | None, question: str | None = None) -> list:
    plan = plan_retrieval(fact_sheet(crew, domain), question)
    return STORE.search(
        plan.query,
        focus_topics=plan.focus_topics,
        background_topics=plan.background_topics,
        top_k=TOP_K,
    )


def test_sleep_request_retrieves_sleep_evidence() -> None:
    results = _retrieved(NOOR, "sleep", "Why is sleep flagged?")

    assert len(results) == TOP_K
    assert all(SLEEP_TOPICS & set(result.passage.topics) for result in results)


def test_activity_request_retrieves_exercise_evidence_not_lighting() -> None:
    results = _retrieved(NOOR, "physical_activity", "Why is activity flagged?")

    assert len(results) == TOP_K
    for result in results:
        assert ACTIVITY_TOPICS & set(result.passage.topics), result.passage.evidence_id
        assert "circadian" not in result.passage.topics


def test_data_quality_request_retrieves_monitoring_evidence() -> None:
    results = _retrieved(CHEN, None, "Can we trust these readings?")

    assert results
    assert all({"monitoring", "autonomy"} & set(result.passage.topics) for result in results)


def test_unrelated_question_does_not_pull_unrelated_evidence_into_an_answer() -> None:
    """An off-topic question gets a conversational reply: no report and no evidence."""
    response = make_agent().explain(
        ExplanationRequest(
            crew_member_id=NOOR,
            domain="sleep",
            question="What is the quarterly revenue forecast?",
            mode="deterministic",
        )
    )

    assert response.generation.question_kind == "greeting"
    assert response.citations == [] and response.evidence_context == []
    assert response.observations == [] and response.suggested_checks == []
    assert response.verification.passed

    # A question about the data still keeps its evidence on the domain being explained.
    response = make_agent().explain(
        ExplanationRequest(
            crew_member_id=NOOR,
            domain="sleep",
            question="Explain the results",
            mode="deterministic",
        )
    )
    cited = [STORE.get(citation.evidence_id) for citation in response.citations]
    assert cited and all(SLEEP_TOPICS & set(passage.topics) for passage in cited)
    assert response.verification.passed


def test_question_about_an_unmonitored_subject_is_marked_as_background_only() -> None:
    """Radiation evidence may be shown, but the answer says no result concerns it."""
    response = make_agent().explain(
        ExplanationRequest(
            crew_member_id=NOOR,
            domain="sleep",
            question="Could cosmic radiation exposure explain this?",
            mode="deterministic",
        )
    )
    cited_topics = {
        topic for citation in response.citations for topic in STORE.get(citation.evidence_id).topics
    }

    assert "radiation" in cited_topics
    notes = [item.text for item in response.uncertainties if "No stored result" in item.text]
    assert len(notes) == 1 and "radiation exposure" in notes[0]
    assert "background only" in notes[0]
    # No sentence about the crew member mentions radiation.
    crew_text = " ".join(
        [response.headline, response.status_summary]
        + [item.text for item in response.observations]
        + [item.text for item in response.interpretations]
    )
    assert "radiation" not in crew_text.lower()
    assert all(not item.evidence_ids for item in response.observations)
    assert response.verification.passed


def test_no_background_note_when_only_monitored_subjects_are_cited() -> None:
    response = make_agent().explain(
        ExplanationRequest(crew_member_id=NOOR, domain="sleep", mode="deterministic")
    )
    cited_topics = {
        topic for citation in response.citations for topic in STORE.get(citation.evidence_id).topics
    }
    unmonitored = {"radiation", "cognition", "cardiovascular", "bone", "muscle", "vision"}

    has_note = any("No stored result" in item.text for item in response.uncertainties)
    assert has_note == bool(cited_topics & (unmonitored | {"behavioral", "sensorimotor"}))
