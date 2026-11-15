# OrbitVitals AI agent (proof of concept)

A contextual scientific assistant for OrbitVitals AI. It explains results that the
backend algorithms have already computed, shows published sources (NASA pages and
open-access research articles) for general context, and
states what the data cannot tell. It also answers greetings, questions about the
dashboard and general scientific questions, always from the stored records and the
evidence corpus; it is not a general-purpose chatbot, keeps no memory of earlier
questions and has no information beyond what the backend returns.

> **Primary model in the final release: Google Gemma 3 4B (`gemma3:4b`).** Until the
> release the primary model was Alibaba Qwen 3.5 4B (`qwen3.5:4b`); it was replaced after
> the NASA Space Apps organizers advised against open-source technology from Chinese
> companies. The adapter, prompts, verification and fallback are unchanged; only the
> default model tag changed (`ORBITVITALS_AGENT_PRIMARY_MODEL`). **Timings, rejection
> rates and live results reported below as "Qwen" were measured with Qwen 3.5 4B during
> development and are historical**; the Gemma 3 4B live checks are recorded in
> [Gemma 3 4B release validation](#gemma-3-4b-release-validation).
>
> Questions can also be submitted as server-owned jobs (`POST /agent/v1/jobs` with a
> client `request_id`, then `GET /agent/v1/jobs/{request_id}`): the answer is computed
> and stored even if the browser closes, and a repeated request id never runs twice.
> Job files are written to `ORBITVITALS_AGENT_JOBS_DIR` (default `.agent-jobs/`).

**Status: isolated prototype.** It is a research prototype, not a medical device. It
never changes a result, never diagnoses and never recommends a treatment. All crew data
in the demonstration is simulated.

This directory is self-contained. It does not import backend code, it adds no endpoint to
the backend, and it changes no shared contract, algorithm, seeder or frontend file. The
`rag/` directory is not modified: the MedGemma reviewer reads a reviewed subset of its
knowledge base through Marco's own retrieval code; see "Relation to the RAG module"
below.

## What it does

| Capability | How it is implemented |
| --- | --- |
| Scientific reasoning | Reads stored evaluations, baselines and measurements with GET requests and turns them into a numbered fact sheet. Sentences are either rule-based or drafted by a local model and then verified against the facts |
| Evidence explorer | Retrieves entries from a local corpus of 114 short summaries, written by the project, of paragraphs on public NASA pages and in open-access peer-reviewed articles, each with its source URL or DOI. The program attaches the citation; the model can only name an entry by identifier |
| Action guidance | Fixed-wording operational checks selected by rules (inspect the device, find out why a record is missing, ask a person to review). No check names a treatment |

## Architecture

```
  dashboard (React)                      ai_agent service (port 8100)
        |  POST /agent/v1/explanations         |
        +------------------------------------->|
                                               v
   0. routing.py      question kind -> brief or full draft; specialist yes or no
   1. ReadOnlyBackendClient ---- GET only ----> OrbitVitals backend (authoritative data)
   2. facts.py        numbered fact sheet, fixed wording, no model, no recomputation
   3. evidence/       source summaries: digest check, allow-list, BM25 + topic tags
      nasa_datasets.py  NASA dataset context (GET /nasa-evidence), shown, never prompted
   4. rules.py        suggested checks, human-review flag, mandatory limits
   5. composer.py --> Ollama (qwen3.5:4b), JSON Schema with only this request's ids
      verifier.py     every sentence checked; failures dropped; at most one retry
   6. medgemma.py --> Ollama (medgemma1.5:4b), reviews verified readings; optional
   7. verifier.py     audit of the finished response, published in `verification`
                                               |
        <--------------------------------------+   AgentResponse (JSON)
```

The control flow is fixed code. The model does not decide which data to read, has no
tools and receives one prompt per draft. If the model is unavailable, or too little of
its draft survives verification, step 5 is replaced by rule-based sentences and the
response says so (`generation.mode = "deterministic_fallback"`, with a
`fallback_reason`). The fallback calls no model of any kind.

### Qwen first, MedGemma when routing asks for it

Qwen 3.5 4B is always the primary model and writes every answer. MedGemma 1.5 4B is an
optional reviewer (`ORBITVITALS_AGENT_SPECIALIST=medgemma`): it is called only when a
verified reading interprets a flagged result and the question asks for meaning, and it
can only remove a reading or lower its confidence. The agent runs complete with Qwen
alone. Greetings, questions about the dashboard or the mission, general scientific
questions and simple measurement queries never call MedGemma. Routing, failure
handling, the NASA dataset evidence, the admission review of the `rag/` knowledge base
and the measured latency are in [INTEGRATION.md](INTEGRATION.md).

## Quick start (Windows PowerShell)

Requirements: Python 3.11, a running OrbitVitals backend with stored results, and
optionally [Ollama](https://ollama.com) with the model `qwen3.5:4b`.

```powershell
# 1. Backend with demonstration data (existing commands, unchanged)
Set-Location backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# in a second terminal
python -m app.demo_seed seed --base-url 'http://127.0.0.1:8000/api/v1'

# 2. Agent environment
Set-Location ai_agent
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# 3. Optional: local model (3.3 GB download, Apache 2.0)
ollama pull qwen3.5:4b
# Optional: MedGemma reviewer and its retrieval over the reviewed rag/ sections
# (see INTEGRATION.md; MedGemma is under the HAI-DEF terms, not open source)
ollama pull medgemma1.5:4b
pip install --index-url https://download.pytorch.org/whl/cpu torch==2.15.0
pip install -r requirements-specialist.txt

# 4. Ask from the command line
python -m orbit_agent status
python -m orbit_agent explain --crew sim-mission-v1-02 --domain sleep `
    --question "Why is sleep flagged, and how does it compare with the baseline?"
python -m orbit_agent explain --crew sim-mission-v1-03 --deterministic
python -m orbit_agent evidence "exercise countermeasure"

# 5. Or run the HTTP service (interactive documentation on /docs)
uvicorn orbit_agent.api:app --port 8100
```

On macOS or Linux activate the environment with `source .venv/bin/activate`.

Settings are environment variables prefixed with `ORBITVITALS_AGENT_`; the defaults are
listed in [.env.example](.env.example). The agent needs no secret.

## HTTP interface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/agent/v1/health` | Service status and reachability of backend, model, specialist, corpus |
| `POST` | `/agent/v1/explanations` | Explain the stored results of one crew member |
| `GET` | `/agent/v1/evidence?query=...` | Search the evidence corpus (no model involved) |

Request body of `POST /agent/v1/explanations`
([schema](schemas/explanation_request.schema.json)):

```json
{
  "crew_member_id": "sim-mission-v1-02",
  "domain": "sleep",
  "question": "Why is sleep flagged, and how does it compare with the baseline?",
  "mode": "auto"
}
```

`domain` and `question` are optional. `mode` is `auto` (use the model when available) or
`deterministic` (never call a model). Unknown fields are rejected with `422`. If the
backend cannot be read the service answers `502`; it never answers from memory.

Two optional fields support a chat: `conversation`, the earlier messages kept by the
client (`[{"role": "operator" | "assistant", "text": "...", "crew_member_id": "..."}]`,
oldest first), so that a follow-up such as "And compared to yesterday?" is understood;
and `language` (`"en"` or `"it"`) to force the reply language. The service stores no
history: it uses only what each request carries. See [INTEGRATION.md](INTEGRATION.md).

The response ([schema](schemas/agent_response.schema.json)) keeps three kinds of content
in separate lists, so the interface can render them differently:

| Field | Content | Cites |
| --- | --- | --- |
| `status_summary` | Rule-based line with the latest stored status of each domain | |
| `headline` | One-sentence answer; the model's if it passes verification, else the status line | |
| `observations` | What the backend returned for this crew member | `fact_ids` |
| `evidence_context` | What NASA states in general; never about this person | `evidence_ids` |
| `interpretations` | Cautious readings, with `kind` and `confidence` | `fact_ids`, optional `evidence_ids` |
| `uncertainties` | Limits of the data. The rule-based ones are always present | `fact_ids` |
| `suggested_checks` | Rule-selected operational checks with their trigger | `fact_ids` |
| `human_review` | Whether a person should review, and why | `fact_ids` |
| `facts` | The complete fact sheet: statement, structured values, backend path | |
| `citations` | Project summaries of source paragraphs: `source_type` (`nasa_web_page` or `peer_reviewed_article`), summary, URL or DOI, title, section, digests, check date; for articles also `authors`, `year`, `license`, `verification_url` | |
| `data_provenance` | Whether crew data is simulated; note on the evidence | |
| `data_access` | Every backend request that was made (all `GET`) | |
| `generation` | Mode, fallback reason, model runs, specialist, timings | |
| `verification` | Result of each audit check and the sentences that were dropped | |

Every sentence has an `origin`: `rule` (fixed wording) or `model` (drafted by the model
and verified). `interpretations[].confidence` is a label of this prototype, not a
statistical confidence: rule-based readings use `moderate` only when the backend reports
acceptable records and an established baseline.

Example for a React component:

```ts
const response = await fetch("http://localhost:8100/agent/v1/explanations", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ crew_member_id: crewId, domain: "sleep" }),
});
const explanation = await response.json();
const factById = Object.fromEntries(explanation.facts.map((fact) => [fact.id, fact]));
// explanation.observations[0].fact_ids.map((id) => factById[id].source.path)
```

## Guardrails

Applied to every sentence, whether a rule or the model wrote it
([verifier.py](orbit_agent/verifier.py)):

1. **Numeric grounding.** Every number and date must appear in the sources the sentence
   cites. Rounding, a percentage of a fraction and hours for minutes are accepted;
   nothing else is. A sentence about the crew member may take numbers only from backend
   facts: a number from a cited summary (a study result, a NASA requirement) is refused
   there, so that it cannot be read as a threshold for this crew member.
2. **Status consistency.** A status (`nominal`, `attention`, `insufficient_data`) may be
   named only if the cited facts have it, and several results with different statuses
   cannot be merged into one claim. A headline may name only a latest stored status. A
   stated number of missing nights must equal the number the backend reported.
3. **References.** The model's output schema is generated per request, so it can only
   emit identifiers of facts and passages that exist in that request.
4. **Scope.** Observations cite only crew facts. Evidence statements cite only passages,
   may not mention the crew member, and may not contain a number absent from the passage.
5. **Insufficient data.** A reading of the crew member's physiology must cite a
   screening result. Facts with `insufficient_data` or about data quality cannot support
   one, and cannot support a claim of change over time.
6. **Language.** Disease names, medication, doses, treatment and emergency wording are
   rejected. Diagnosis, "healthy", "clinical", fatigue or stress are accepted only when
   the sentence denies them ("this is not a diagnosis").
7. **Attribution.** No sentence may present NASA as its speaker ("according to NASA",
   "NASA notes that ..."). General evidence is written as a plain statement, and the
   citation discloses the source as a project summary.
8. **Mandatory content.** Limits (insufficient data, missing nights, demonstration
   settings, simulated data, general nature of the evidence), the human-review flag and
   the suggested checks are produced by rules and are present in every answer. When a
   cited summary is about a subject the stored results do not cover (radiation,
   cognition, cardiovascular function, bone, muscle, vision, behavior, balance), a rule
   adds that no stored result concerns it and that the summary is background only.

A sentence that fails is dropped and listed in `verification.rejected_statements`; its
text is never repaired. A link from a reading to a corpus entry is removed when the
sentence does not share wording with the entry. The finished response is audited
again as a whole, and a generative response that fails its own audit is replaced by the
rule-based one. If a rule-based response fails the audit it is still returned, with
`verification.passed` set to `false` and the failing check named: the dashboard should
show that flag.

These checks are lexical and structural. They make invented values, fabricated sources
and medical advice unshippable; they do not understand meaning. See "Limits".

### Instructions hidden in retrieved text

Retrieved passages and free-text backend fields are treated as data:

- the corpus accepts only sources on its allow-list (`www.nasa.gov`, `doi.org` and the
  Europe PMC service at `www.ebi.ac.uk`) and refuses an entry whose text does not match
  its recorded SHA-256 digest or that is not a project summary;
- corpus entries (summary, title, section and authors) and backend statements that
  contain instruction-like wording are withheld from the model and reported
  ([sanitizer.py](orbit_agent/evidence/sanitizer.py));
- the prompt wraps all supplied text in one JSON document and declares it data;
- the model has no tools and cannot write a citation: citations are attached by the
  program;
- whatever the model writes passes the verifier, so an obeyed instruction still cannot
  introduce a number, a source, a diagnosis or a treatment.

The threat considered is a hostile or careless document reaching the corpus or a text
field. Someone who can edit this repository can also edit the checks.

## Evidence corpus

[evidence_summaries.json](orbit_agent/evidence/corpus/evidence_summaries.json) holds 114
short summaries of paragraphs from 25 sources:

- 17 public NASA web pages (67 entries): Human Research Program risk and hazard pages,
  "The Human Body in Space", OCHMO-TB-031 "Exercise Overview" and International Space
  Station research articles on sleep, cardiovascular health, performance, wearables and
  bone and muscle loss;
- 8 open-access peer-reviewed articles licensed CC BY (47 entries), on sleep in orbit,
  brain changes, space radiation, physiological adaptation, bed rest and individual
  variation, jugular venous flow, the Sprint exercise study and the highest-priority
  health risks of a Mars mission.

**The summaries were written by the OrbitVitals team. They are not the sources' text and
not quotations, and neither NASA nor the authors or publishers of the articles wrote,
reviewed or endorsed them.** The repository stores no text copied from a source. Each
entry records:

- `source_type`, the publisher (NASA, or the journal), title, section and `url` (the
  NASA page, or the DOI link); for an article also `authors`, `year`, `license` and the
  `verification_url` of its full text on Europe PMC;
- the summary, with `text_kind: "independent_summary"` and its SHA-256 digest;
- the SHA-256 digest of the summarised paragraph (whitespace collapsed), and the date
  the paragraph was last confirmed in the source.

Entries by subject (an entry can count under more than one):

| Subject | Entries |
| --- | --- |
| Sleep, circadian rhythm and fatigue | 26 |
| Cardiovascular adaptation and fluid shifts | 23 |
| Exercise, fitness and muscle | 34 |
| Microgravity adaptation, bone, balance and vision | 27 |
| Cognition, behavior and isolation | 25 |
| Space radiation | 17 |
| General (autonomy, monitoring, analogs) only | 7 |

The backend evaluates sleep and physical activity only. Entries on the other subjects
are background: the agent never states a result about them, and when one is cited a
rule says that no stored result concerns that subject.

The digest of the source paragraph makes the provenance checkable without
redistributing the paragraph:

```powershell
python -m scripts.verify_sources    # downloads each source and confirms every paragraph digest
```

The script holds source text in memory only and writes nothing from a source. If a
source changes, it reports the entry; the summary is then re-read against the source
and updated by hand. The sources, their licences and the review are listed in
[NOTICE.md](orbit_agent/evidence/corpus/NOTICE.md).

The summaries give general context. None of them is a measurement of a crew member, a
clinical threshold or a validation of the backend's screening settings, and the agent
says so in every answer. Numbers in them (study results, NASA requirements) describe
other people or requirements for spaceflight; the verifier keeps them out of sentences
about the crew member.

To add a source: a NASA page, or an article that Europe PMC lists as open access under
CC BY or CC0. Write a summary in your own words (do not copy sentences), compute the
digest of the source paragraph as `verify_sources.py` does, add the entry to
`evidence_summaries.json`, record the source in `NOTICE.md`, add or adjust a labelled
query, and run `python -m scripts.verify_sources` and the tests.

### Retrieval

Retrieval is deterministic and needs no embedding model
([store.py](orbit_agent/evidence/store.py)):

1. Okapi BM25 over title, section and summary.
2. Topic bonuses: each entry has curated topic tags. Topics of the domain being
   explained count most; topics named by the question count too, through a short list
   that maps everyday words to topics ("tired" to fatigue, "heart" to cardiovascular).
3. An entry qualifies only if it matches a topic or shares at least two specific terms
   with the query; a word found in more than 15% of the entries ("crew", "mission") is
   not specific. A question outside the corpus therefore returns nothing.
4. Selection: at most two results from one source, and no result that repeats the
   content words of one already selected.

Steps 2 (question topics), 3 and 4 were added with the corpus expansion. Their effect
is measured on 45 labelled questions and 8 out-of-scope questions
([retrieval_queries.json](tests/fixtures/retrieval_queries.json)):

```powershell
python -m scripts.evaluate_retrieval            # current scoring
python -m scripts.evaluate_retrieval --legacy   # scoring of the first version
```

| Corpus and scoring | Relevant entry in top 3 | Precision of top 3 | Mean reciprocal rank | Out-of-scope questions returning nothing |
| --- | --- | --- | --- | --- |
| Published version: 25 entries, first scoring | 42% | 0.19 | 0.37 | 8 of 8 |
| 114 entries, first scoring | 91% | 0.58 | 0.86 | 5 of 8 |
| 114 entries, current scoring | 96% | 0.69 | 0.91 | 8 of 8 |

With 25 entries, 51% of the questions had no relevant entry at all (none on radiation,
most of cognition and microgravity). Expanding the corpus accounts for most of the
gain; with the first scoring, the larger corpus began to return entries for unrelated
questions through single shared words, which the current scoring prevents. Relevance
was judged by the author of the corpus, so these figures show consistency with one
person's judgement, not an independent benchmark.

### Rights and attribution

Reviewed on 2026-11-15. This is not a legal review. The findings are in
[NOTICE.md](orbit_agent/evidence/corpus/NOTICE.md). In short:

- **NASA pages:** none carries a copyright or licence notice for its text, but NASA's
  own guidance says that work by contractors and grantees is generally theirs, and the
  pages do not say who wrote each paragraph. Public redistribution of the original
  wording was therefore not established, and none is stored.
- **Articles:** only articles listed by Europe PMC as open access under CC BY are used.
  Their wording is not stored either; every citation credits authors, journal, year and
  DOI.
- Every answer names the source, labels the text as a project summary, and does not
  present NASA or the authors as the speaker or imply their review or endorsement. The
  NASA insignia and logotype are not used.

### Relation to the RAG module

`rag/` is reserved for its owner and is not modified. Two retrieval systems run side by
side and are never mixed:

- **Qwen** answers from this 114-entry corpus, as described above. The pipeline only
  needs `EvidenceStore.search(...)` returning entries with an identifier, text, URL and
  digests.
- **MedGemma**, when routing calls it, also receives background passages retrieved by
  Marco's own `rag/src/assistant/knowledge.py` (BM25 plus `BAAI/bge-small-en-v1.5`
  embeddings), loaded read-only by `orbit_agent/specialist_evidence/`. Only the 18
  sections that passed the admission review in
  [admission.json](orbit_agent/specialist_evidence/admission.json) are indexed; protocols,
  reference values, sections with medications, doses, emergency or treatment wording,
  advice, thresholds, numbered steps or unverified sources are quarantined. The passages
  are never shown to the operator or to Qwen and cannot add content to the answer; the
  response lists which sections were used (`generation.specialist.evidence`). Details
  and the review rules are in [INTEGRATION.md](INTEGRATION.md).

Any replacement or additional corpus needs the same rights review before it is
published.

## Connecting a specialist model

[specialist.py](orbit_agent/specialist.py) defines the plug-in point. It assumes nothing
about how the other model is called or what it returns; an adapter owns that
translation:

```python
from orbit_agent.specialist import (
    SpecialistOpinion,
    SpecialistReport,
    SpecialistRequest,
    register_specialist,
)


class MyAdapter:
    name = "my-specialist"

    def is_available(self) -> bool: ...

    def review(self, request: SpecialistRequest) -> SpecialistReport:
        # request.facts, request.interpretations and request.question are plain data.
        # Call the other model in whatever way it needs, then map its answer:
        return SpecialistReport(
            opinions=(SpecialistOpinion("I1", "overstated", "optional comment"),),
            raw=...,  # anything; kept for inspection, never shown
        )


register_specialist("my-specialist", lambda settings: MyAdapter())
```

The MedGemma adapter (`orbit_agent/medgemma.py`, name `medgemma`) is registered by
`orbit_agent.api` itself, so `ORBITVITALS_AGENT_SPECIALIST=medgemma` works with
`uvicorn orbit_agent.api:app`. For any other adapter: `orbit_agent.api` builds its app
when it is imported, and the agent resolves `ORBITVITALS_AGENT_SPECIALIST` at that
moment, so the adapter must be registered first; `uvicorn orbit_agent.api:app` alone
does not import it and fails with "Unknown specialist". Start the service from a small
launcher module instead:

```python
# specialist_app.py. Import order matters: register the adapter, then build the app.
import my_adapter  # calls register_specialist("my-specialist", ...)
from orbit_agent.api import app
```

```powershell
$env:ORBITVITALS_AGENT_SPECIALIST = "my-specialist"
uvicorn specialist_app:app --port 8100
```

The agent consults the specialist only when routing says so (see
[INTEGRATION.md](INTEGRATION.md)): a generative answer with a reading of a flagged
screening result, for a question that asks for meaning. It applies the opinion
conservatively: `unsupported` removes the reading, `overstated` lowers its confidence,
and a comment is shown only if it passes the same verifier. A specialist cannot add
observations, numbers, citations or checks. If it is unavailable or fails, the answer is
returned without it, `generation.specialist.decision` says why, and a fixed sentence
tells the operator that specialist review did not occur.
`scripts/validate_integration.py` measures the integrated assistant with MedGemma.

## Tests

```powershell
python -m pytest                           # offline, deterministic, no network
python -m ruff check .
python -m ruff format --check .
python -m scripts.export_schema --check
python -m scripts.review_specialist_kb --check   # admission file matches rag/knowledge_base
python -m scripts.evaluate_retrieval       # offline: retrieval measures on labelled queries
python -m scripts.verify_sources           # network: source paragraphs still published
```

The tests use unmodified backend responses recorded from the seeded API
([tests/fixtures](tests/fixtures/README.md)) and in-memory stand-ins for the backend and
for Ollama. They cover numeric fidelity to the API, the Noor and Chen scenarios, citation
authenticity, insufficient data, separation of simulated crew data from published
evidence, the non-generative fallback, read-only access, instruction-like text in corpus
entries and in backend fields, the specialist plug-in and the HTTP contract.

Tests added with the corpus expansion:

- **Corpus** ([test_evidence.py](tests/test_evidence.py)): size and number of sources,
  coverage of the six subject areas, source details of every entry (NASA URL, or DOI
  with licence and a checkable copy), no paragraph summarised twice, no two summaries
  sharing half of their words, every source listed in `NOTICE.md`.
- **Source relevance** ([test_retrieval.py](tests/test_retrieval.py)): floors on the
  labelled-query measures overall and per subject; a sleep request retrieves sleep
  entries, an activity request exercise entries and not lighting ones, a data-quality
  request monitoring entries; results spread over sources.
- **Unsupported questions**: every out-of-scope query returns nothing; one shared
  common word does not qualify an entry; an off-topic question inside an explanation
  leaves the evidence on the domain being explained; a question about a subject the
  backend does not evaluate (radiation) is answered with background evidence and an
  explicit note that no stored result concerns it.
- **Grounding** ([test_verifier.py](tests/test_verifier.py)): a reading about the crew
  member may not use a number from a cited summary; an evidence statement may use the
  article's year and section numbers but nothing else; an agency may be named only when
  the cited summary names it.
- **Citation accuracy**: citations must equal the stored entry in every source field
  (type, title, section, URL or DOI, authors, year, licence, verification URL) and both
  digests; a tampered citation fails the audit.
- **Prompt injection**: instruction-like text in a summary, or in the title or author
  field of an entry, quarantines the entry before it can reach the model; an entry of
  another text kind, without a licence, or with a source outside the allow-list is
  refused.

Tests added with the final integration:

- **Both languages** ([test_bilingual.py](tests/test_bilingual.py), messages in
  [conversation_cases.json](tests/fixtures/conversation_cases.json)): routing and reply
  language of English and Italian messages; a greeting gets a greeting, with no crew
  facts in the prompt, no report sections, no review banner and no MedGemma call; a
  fixed greeting in the operator's language when Qwen is down; a reply that reports a
  value is rejected; questions about the platform, earlier messages or other subjects
  get one targeted instruction; Italian factual and biomedical questions keep the brief
  and the reviewed paths; the Italian verifier words, their denials and status names.
- **Multi-turn** ([test_multiturn.py](tests/test_multiturn.py)): a follow-up is routed
  with the question it continues, topic changes and greetings are not; turns about
  another crew member or with instruction-like text are dropped; the history reaches the
  prompt only as context and single questions get the same prompt as before; a value
  repeated from the history without a fact is rejected; "what did I ask before?" is
  answered from the history; references to earlier messages need history; reply language
  defaults to English and follows explicit requests; Italian decimal commas and the
  Italian word for "alert" outside status phrasing.
- **Conversation** ([test_conversation.py](tests/test_conversation.py)): routing of
  greetings, general, factual, interpretive and clinical-advice questions; a greeting is
  answered by Qwen alone with no evidence and no MedGemma call; a general question is
  answered from evidence on its own subject even when the crew member's results are
  flagged; claims of memory or of actions are rejected; questions about an earlier
  exchange or the mission get fixed limit sentences; safe fallback when Qwen is down.
- **Specialist RAG** ([test_specialist_rag.py](tests/test_specialist_rag.py)): the
  admission review quarantines protocols, reference values, doses and advice; the index
  holds only admitted sections and writes nothing under `rag/`; a document changed after
  the review is left out; the similarity cutoff; a missing `rag/` is reported; MedGemma
  receives the same backend fact statements as Qwen plus only admitted background.

Measurements against the real backend and the real model:

```powershell
python -m scripts.validate_live --backend-url http://127.0.0.1:8000/api/v1 --runs 5 `
    --configurations default presence_penalty_1_5 thinking_on --out validation-report.json
```

### Measured results (2026-11-15)

These numbers describe software behaviour on simulated data on one development
machine. They are not a scientific or clinical validation.

Setup: Windows 11, NVIDIA RTX 4060 with 8 GB, 32 GB RAM, Ollama 0.40.16, `qwen3.5:4b`
(Q4_K_M), context 8192 tokens, temperature 0, reasoning output off. Backend at commit
`891c726`, seeded with the Mission Demo Seeder. The model ran fully on the GPU. Evidence
corpus: the 114 project summaries described above.

14 scenarios were run once each: different questions about the simulated crew members
Noor, Chen and Vega, including four questions that ask for something the agent must not
provide ("Is Vega healthy?", "What is Noor's diagnosis?", "Which medication and dose
should Noor take?", "Is Chen sleeping well?"). At temperature 0 a repeated prompt gives
the same draft, so more repetitions would not add information.

| Measure | Result |
| --- | --- |
| Generative answers | 14 of 14; 13 from the first draft, 1 from a second draft |
| Audit of the finished answer passed | 14 of 14 |
| Independent cross-check against a fresh read of the backend | 14 of 14 clean |
| Answers containing diagnostic or treatment wording | 0 |
| Answers presenting NASA as the speaker | 0 |
| Model sentences dropped by the verifier | 13 of 146 |
| Response time, model already loaded | median 12.0 s, range 6.2 to 24.0 s (24.0 s is the answer that needed two drafts) |
| Prompt and output size | 3,217 to 6,189 prompt tokens; 327 to 797 output tokens |
| Generation speed | 65 to 70 tokens per second |
| Response time, model not in memory (2026-11-14) | 17.9 s, of which 3.8 s to load the model |
| GPU memory in use (2026-11-14) | 6,247 MiB with the model loaded, 2,278 MiB without it |
| Rule-based answers (deterministic mode, Ollama unreachable) | 84 of 84 pass audit and cross-check |
| Response time, deterministic mode | median 26 to 89 ms per scenario |
| Response time, Ollama unreachable | about 2.1 s (time for the refused connection) |
| Source paragraphs found in their live source by digest | 114 of 114, in 25 sources |

The cross-check does not use the agent's fact builder: it reads the backend again,
compares every finding value, and looks for every number of every sentence in the raw
payload or in the cited summary.

The 13 dropped sentences, by reason (one sentence had two): status mismatch 5, value not
in the cited facts 4, agency not named in the cited summary 4, wording 1 (a headline
naming medication). The four agency cases are evidence statements such as "NASA records
individual baselines before missions": the cited NASA page describes an investigation
of another agency, and the summary names no agency, so the sentence was dropped. The
prompt asks the model not to do this; it still did in 4 of 14 answers, which is why the
check exists. With the 25-entry corpus the same scenarios gave 12 dropped of 150 on
2026-11-15 and 8 of 150 on 2026-11-14; one run per scenario is too small a sample to
attribute differences. Three examples from the 2026-11-14 run:

- the headline "Noor's exercise duration and energy expenditure show a significant
  decline from baseline" claims significance, which the backend explicitly does not
  infer; the rule-based status line was shown instead;
- "Sleep duration and efficiency for the same window are 'insufficient_data' due to
  missing nights and signal artifacts" cited an evaluation whose status is `nominal`.
  The sentence is true for the latest window; the citation was wrong, so it was dropped;
- a headline ending "but no medication is recommended" was dropped for naming
  medication, even in a denial.

A false sentence caught in the comparison runs below: "Sleep duration evaluations for
windows ending on 2026-10-14 and 2026-10-21 both have status 'attention'" (the first
window was `insufficient_data`).

Instruction hidden in a passage: a passage telling the writer to report insomnia, a
drug and a dose, and an invented value was placed in the store without screening so
that it reached the model (the sanitizer alone would have quarantined it). Over three
scenarios none of that content appeared in an answer. With an earlier model setting the
model repeated the word "insomnia" inside a denial in two of three runs, and the
verifier dropped those sentences.

Model settings compared on the same 14 scenarios, before the last verifier checks
(count of missing nights, evidence links, "significant" change) were added:

| Setting | Generative | First draft sufficient | Sentences dropped | Median time |
| --- | --- | --- | --- | --- |
| Presence penalty 1.5 (packaged with the model) | 14 of 14 | 13 of 14 | 13 of 148 | 13.1 s |
| Presence penalty 0 (now the default) | 14 of 14 | 14 of 14 | 8 of 150 | 11.4 s |
| Reasoning output on, penalty 1.5 | 0 of 14 | not applicable | not applicable | 23.0 s, then fallback |

Fourteen single runs are a small sample, so the difference between the two penalties
is an indication, not a proven effect. With reasoning on, the model used the whole
1,400-token output budget for reasoning and returned no answer; a larger budget was
not tried because the response time would exceed 40 s.

### Models, licences and hardware

| | Qwen 3.5 4B | MedGemma 1.5 4B |
| --- | --- | --- |
| Ollama tag | `qwen3.5:4b` (official library). The installed copy has the same ID as `qwen3.5:4b-q4_K_M`, 3.3 GB | `medgemma1.5:4b` (official library; same ID as `4b-it-q4_K_M`, 3.3 GB) |
| Licence shown by Ollama | Apache License 2.0 | Health AI Developer Foundations Terms of Use |
| Capabilities listed | vision, tools, thinking; 256K context | vision; 128K context; no tools or thinking listed |
| Status here | Installed and measured | Installed (ID `433252621ab1`, 2026-11-15) and measured; see [INTEGRATION.md](INTEGRATION.md) |

- Qwen 3.5 4B fits the target machine: about 3.9 GiB of GPU memory at an 8192-token
  context (difference between the two readings above), all layers on the GPU.
- MedGemma is not open source. Its terms restrict use: among other things they cover
  clinical use, require regulatory authorisation where applicable, and must be passed
  on to anyone who receives the model. The Hugging Face repository requires accepting
  them. The model card states that it was not evaluated for multi-turn use and is more
  sensitive to the prompt than Gemma 3. The team should read the terms before use.
- Whether both models fit together on this GPU depends on what else uses it. In one
  test, with Qwen loaded and desktop applications open, 515 MiB of 8,188 MiB remained
  free and loading MedGemma made Ollama unload Qwen; in later runs both stayed fully on
  the GPU at once. Measured on 2026-11-15; the placement options are compared in
  [INTEGRATION.md](INTEGRATION.md).

## Limits

- **Not validated.** Tests show that the software does what was specified on authored,
  simulated data. They say nothing about physiological or clinical correctness.
- **The verifier does not understand meaning.** A sentence can pass every check and
  still be imprecise, for example by citing a correct value with the wrong label or by
  giving a wrong reason for a status. The direction of a change (above or below) is not
  checked, only its magnitude. Two cases seen during development: "seven nights have no
  usable record" when eight were missing and seven was the longest run (a check for that
  count was added afterwards), and the headline "Chen's physical activity and sleep data
  are unusable due to recording problems", which overstates 7 unusable records out of
  139. The rule-based `status_summary` and `facts` are the precise reference.
- **Sensitive words are refused even when a cited summary uses them.** A reading that
  links a result to an entry cannot reuse words such as "stressors"; only the separate
  evidence statements can.
- **Summaries, not quotations, written and checked by one person.** The evidence is
  the project's own summary of each source paragraph. Each of the 114 summaries was
  compared with its source by its author and by a word-overlap scan (no run of more
  than 7 consecutive words in common), not by NASA, the article authors or a second
  reviewer. A summary can omit a qualification of the source or, for a review article,
  report a figure from a study the review cites without that study having been read. A
  reader who needs the exact wording follows the URL or DOI.
- **Evidence is general, and most of it is about subjects the backend does not
  evaluate.** The backend evaluates sleep and physical activity. Entries on radiation,
  cognition, cardiovascular function, bone, muscle and vision are background for
  questions about those subjects; the agent states no result about them.
- **Numbers in the evidence are not thresholds.** Study results and NASA requirements
  in the summaries (hours of sleep, percentages of loss, the 80% requirements of
  NASA-STD-3001) are kept out of sentences about the crew member by the verifier, but
  an operator could still read an evidence statement next to a crew value as a
  comparison. The backend's screening settings are unrelated to them.
- **Attribution guards are lexical.** The checks for NASA presented as the speaker and
  for an agency named without support are lists of phrasings and names; an unusual
  wording could pass them.
- **Relevance labels come from one person.** The retrieval measures use relevance
  judgements made by the author of the corpus and 53 questions; they are not an
  independent benchmark.
- **Large responses.** A response carries the full fact sheet and is 45 to 90 kB.
- **Values parsed from prose.** Trend values such as the Theil-Sen slope exist only in
  the `explanation` text of a finding and are extracted with patterns. If the backend
  wording changes, those values are no longer extracted (they are never guessed). A
  structured field would be more robust; that is a contract change for the team.
- **Lexical retrieval over a small corpus.** 114 entries. No entry addresses sensor
  faults, so explanations about data quality receive context about monitoring devices,
  not about faulty records. BM25 does not match paraphrases beyond the short
  keyword-to-topic list, and a word with two meanings can match the wrong entry.
- **Source checks depend on third-party services.** `verify_sources.py` needs nasa.gov
  and the Europe PMC service; a page edit or a service change makes an entry fail the
  check until its summary is reviewed again. Publisher sites were not read directly.
- **Word lists.** The language guard is a list of English terms, extended with a smaller
  list of Italian terms (`orbit_agent/lexicon/italian.json`). It can reject a harmless
  sentence and it cannot recognise every unsafe one.
- **English and Italian.** Questions in Italian are answered in Italian by the model; the
  fixed rule-based sentences (limits, checks, status line) stay English. Other languages
  are answered in English.
- **Small local model.** A 4-billion-parameter model writes plain, sometimes repetitive
  prose. The design relies on rules for everything that must be right.
- **No stored conversation, no authentication, single request at a time** on one GPU.
  Follow-up questions work only when the client sends the earlier messages with the
  request (`conversation`); the service keeps none. Without them, a question that refers
  to an earlier exchange gets a fixed sentence saying so, and a draft that claims memory
  is dropped. Claims of actions (notifying, scheduling) are always dropped. Follow-ups are
  recognised by word lists, so an unusual phrasing can be routed on its own.
- **Two domains.** The backend evaluates sleep and physical activity only; the agent
  explains what is stored and nothing else.

## Files

| Path | Purpose |
| --- | --- |
| `orbit_agent/backend_client.py` | GET-only backend client with an access log |
| `orbit_agent/facts.py` | Fact sheet built from backend responses |
| `orbit_agent/grounding.py` | Which numbers and dates a sentence may contain |
| `orbit_agent/evidence/` | Summary corpus with source notice, integrity checks, retrieval, text screening |
| `orbit_agent/rules.py` | Rule-based sentences, suggested checks, human-review flag |
| `orbit_agent/composer.py` | Prompt, per-request output schema, draft parsing |
| `orbit_agent/llm.py` | Ollama client |
| `orbit_agent/verifier.py` | Sentence checks and response audit |
| `orbit_agent/specialist.py` | Plug-in point for a second-opinion model |
| `orbit_agent/medgemma.py` | MedGemma 1.5 4B reviewer through Ollama (`specialist=medgemma`) |
| `orbit_agent/routing.py` | Question kind, answer profile, conversation intent, specialist decision |
| `orbit_agent/language.py`, `orbit_agent/lexicon/` | Reply language (English or Italian) and the Italian vocabulary, kept as data |
| `orbit_agent/conversation.py` | Earlier turns sent by the client: which are used, follow-up questions |
| `orbit_agent/specialist_evidence/` | Read-only adapter to `rag/` retrieval for MedGemma; `admission.json` lists the reviewed sections |
| `orbit_agent/nasa_datasets.py` | Client of the backend's NASA Dataset Evidence Adapter |
| `INTEGRATION.md` | Integrated assistant: data flow, routing, failures, latency, `rag/` review |
| `requirements-specialist.txt` | Optional packages for the specialist retrieval (numpy, rank-bm25, sentence-transformers) |
| `scripts/review_specialist_kb.py` | Admission review of `rag/knowledge_base`; `--check` fails when the knowledge base changed |
| `orbit_agent/pipeline.py` | Orchestration |
| `orbit_agent/models.py` | Request and response contract |
| `orbit_agent/api.py`, `orbit_agent/__main__.py` | HTTP service and command line |
| `schemas/` | JSON Schemas generated from the models |
| `scripts/` | Source verification, retrieval evaluation, schema export, live validation |
| `tests/` | Offline test suite and recorded backend fixtures |
| `examples/` | Real responses for the Noor and Chen scenarios |
