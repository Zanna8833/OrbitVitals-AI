# Integrated assistant: Qwen + MedGemma + NASA evidence

One assistant, one HTTP service (`ai_agent`, port 8100). Qwen 3.5 4B writes every answer.
MedGemma 1.5 4B reviews Qwen's verified readings when routing asks for it. Two retrieval
systems run side by side: Qwen's 114-entry summary corpus, and Marco's `rag/` retrieval,
used only to give MedGemma background on the sections that passed an admission review.
When a question asks for it, the backend's NASA Dataset Evidence Adapter adds bed-rest
research context. The OrbitVitals backend stays the only source of crew data. Research
prototype on simulated crew data; not a medical device.

## Data flow

```
operator question
   |
   v
routing.py            question kind: none | greeting | general | factual | interpretive
   |                  | clinical_advice -> answer profile: conversation | general | brief
   |                  | full (sentence counts and output budget of Qwen's draft)
   v
backend (GET only) -> facts.py   crew measurements, baselines, quality, evaluations
   |                             every record must belong to the requested crew member
   +-> evidence store            114 summaries, BM25 + topic tags, citations by digest
   |                             (not searched for a greeting)
   +-> nasa_datasets.py          GET /nasa-evidence?topic=... (only if the question asks)
   v
Qwen (qwen3.5:4b) -> verifier    draft limited to this request's fact and evidence ids;
   |                             each sentence checked; failed sentences dropped
   v
routing: specialist?  only for a verified reading of a flagged result (attention/alert),
   |                  and only for a question asking for meaning
   v
specialist_evidence/  rag/src/assistant/knowledge.py (BM25 + bge-small embeddings) over
   |                  the 18 admitted sections only; at most 2 passages with embedding
   |                  similarity >= 0.70 to the review query
   v
MedGemma (medgemma1.5:4b)        sees the verified readings, the backend facts they cite
   |                             (the same statements Qwen saw) and the background
   |                             passages; verdicts: supported | overstated | unsupported
   |                             | no_opinion
   v
conservative merge -> audit     unsupported -> reading removed; overstated -> confidence
                                low; comment shown only if it passes the verifier; the
                                whole response is audited again
```

What each source may do:

| Source | Authority | Reaches which model? |
| --- | --- | --- |
| OrbitVitals backend (`/api/v1`) | Only source of crew measurements, baselines, data quality and evaluations. Read with GET only; never recomputed | Qwen (all numbered facts) and MedGemma (the facts the readings cite, identical wording) |
| Evidence corpus (114 project summaries) | General research context, cited by digest | Qwen, by identifier; citations attached by code |
| `rag/knowledge_base`, admitted sections (Marco's specialist RAG) | Background for the specialist review only | MedGemma only. Never shown to Qwen or the operator; the response lists the sections used |
| NASA Dataset Evidence Adapter (`/api/v1/nasa-evidence`) | Ground-analogue research context about two NASA bed-rest datasets | Neither. Attached by code with fixed wording |
| Qwen | Writes the explanation | n/a |
| MedGemma | Reviews Qwen's verified readings; can remove or soften, never add | n/a |

The kinds of material stay apart in the response: simulated crew values from the backend
in `facts` and `observations`, literature in `citations`
and `evidence_context`, NASA dataset metadata in `dataset_evidence`, specialist
background in `generation.specialist.evidence`.

MedGemma's verdicts change nothing in the backend facts, the status line, the observations,
the suggested checks or the human-review flag. A verdict is a model's opinion and is
labelled as such in the response (`generation.specialist.notice` and a fixed sentence).

## Routing (`orbit_agent/routing.py`)

| Question kind | Example (English / Italian) | Qwen draft (profile) | MedGemma |
| --- | --- | --- | --- |
| `greeting` (conversation) | "Hello!", "ciao", "Thanks", "What can you do?", "Come funziona OrbitVitals?", "What's the weather today?", "Ti ricordi cosa ti ho chiesto prima?" | conversation: headline only, no crew facts in the prompt, no evidence search, 200 tokens max | never |
| `general` | "How does microgravity affect bones in general?", "What does the attention status mean on the dashboard?", "Quanto dura la missione?" | general: headline, up to 3 evidence statements, 0-1 observation and reading, 800 tokens max | never |
| `factual` | "What was Noor's latest sleep duration?", "Quanto ha dormito Crew A?" | brief: 1-2 observations, 1 reading, 500 tokens max | never |
| `clinical_advice` | "Which medication should Noor take?" | full; no advice is given | never |
| `interpretive` / `none` | "Why is Crew B's sleep declining?", "Perché il sonno è peggiorato?" | full, 1,400 tokens max | if a verified reading interprets a flagged result |

The classifier is a fixed list of patterns, checked in this order: clinical advice;
conversation (a greeting, thanks or acknowledgement with at most two other words, or a
short question about the assistant or about OrbitVitals); general (a general cue such
as "in general", "dashboard", "mission", "spaceflight" with no reference to a crew
member or a measurement); conversation again when the message has no subject the
assistant can answer from (no crew member, no health or data topic, no space-health
topic); factual; interpretive. A greeting attached to a real question ("Hi, why is
Noor's sleep flagged?") is classified by the question.

### Conversation and languages

Root cause of the report that "ciao" produced a physiological analysis (fixed
2026-11-15): the classifier knew only English greetings, and every message it could not
classify fell through to `interpretive`, the full report. Even a recognised English
greeting was returned with the data limits, the suggested checks and the human-review
flag, which the dashboard shows as "Limits", "Checks a person could do" and "Worth a
review by the medical team".

Now:

- A message is conversation when it greets, thanks, asks about the assistant or the
  platform, or has no subject the records or the evidence could answer (small talk, a
  request outside OrbitVitals, a bare "why?" that would need an earlier message).
- Qwen gets no crew facts for a conversational reply, and one short instruction for what
  the message asks (`routing.conversation_intent`): greeting, question about the
  assistant or the platform (restating a fixed description of what the code does,
  `composer.PLATFORM_DESCRIPTION`), reference to an earlier message, or request outside
  OrbitVitals.
- A conversational response has a headline and nothing else: no observations, readings,
  evidence, limits, suggested checks, and `human_review.recommended: false`, because it
  presents no result. `facts` and `status_summary` are still returned for the dashboard.
  If Qwen is unavailable or its reply fails the verifier, a fixed greeting in the
  operator's language is returned, not a status report.
- Language (`orbit_agent/language.py`): English by default. Italian when the request sets
  `language: "it"`, when the operator asks for it ("answer in Italian", "rispondi in
  italiano"), or when the operator writes in Italian (a count of frequent words of each
  language; `REPLY_LANGUAGE_DETECTION=false` limits Italian to explicit requests). A
  message too short to tell ("Crew A?") keeps the language of the previous operator
  message. An Italian reply keeps status names such as 'attention' verbatim, so the
  status checks still apply. Other languages are answered in English. The system prompt
  of an English reply is exactly the one validated earlier.
- The Italian vocabulary (routing cues, verifier word lists) and the fixed Italian
  sentences are data in `orbit_agent/lexicon/italian.json`, so the source code stays ASCII
  English. Every verifier guard (medication and dose words, diagnosis and health claims
  with negation, status names and paraphrases, claims of change, NASA as the speaker,
  claims of memory or actions) also matches the Italian words. The Italian lists are
  smaller than the English ones and were written by one person: they are a first version,
  not a reviewed medical vocabulary.
- The fixed rule-based sentences of a data answer (limits, suggested checks, the status
  line, notices) are still English. An Italian data answer therefore mixes Italian model
  sentences with English fixed sentences; translating the fixed sentences needs a reviewed
  Italian version of each.
- Italian status words count as naming a status only in status phrasing ("stato di
  allerta"), and a comma followed by one or two digits is a decimal comma ("52,5" is
  52.5). Both rules were added after live drafts were wrongly rejected ("nessun segnale di
  allerta" for a 'nominal' result) or wrongly accepted ("52,5" read as 52 and 5). "241,667"
  is read both ways and passes only if one reading is grounded in the cited facts.

### Multi-turn conversation (`orbit_agent/conversation.py`)

Two different things, kept apart:

- **Chat history** is kept by the client (the dashboard). With each request it may send the
  earlier messages in `conversation`: `[{"role": "operator" | "assistant", "text": ...,
  "crew_member_id": ..., "domain": ...}]`, oldest first.
- **Model context** is what the model receives for one request: the last 8 of those turns
  (`CONVERSATION_MAX_TURNS`), each cut to 600 characters. The agent stores nothing between
  requests; `generation.context_turns` reports how many turns were used. With no
  `conversation`, a request behaves exactly as before.

How the turns are used:

- A follow-up without a subject of its own ("And compared to yesterday?", "Why?", "E
  rispetto a ieri?", "What could that mean?") is routed together with the earlier
  operator question it continues (walking back at most three operator turns to one that
  names a subject). The joined text drives routing, evidence retrieval, NASA dataset topics
  and MedGemma's review query; the prompt shows it as `question_in_context`.
- A message with a subject of its own (a crew member, a health domain, space science)
  starts or returns to a topic and is routed on its own ("Back to the sleep: is it getting
  worse?"). Greetings, thanks and questions about the assistant stay conversation.
- An explicit language request is removed before routing ("Rispondi in italiano: e
  ieri?" is routed as "e ieri?").
- The turns reach the model as `conversation_so_far`, marked as context that is not facts
  or evidence. Numbers, dates and statuses must still come from the backend facts of this
  request: the verifier rejects a value repeated from the history when no fact holds it.
- Turns about another crew member (`crew_member_id` differs, or the text names another
  crew member listed in `CREW_ALIASES`, such as "Crew A" or "Vega") and turns with
  instruction-like text are dropped. A model sentence naming another crew member fails
  the `crew_identity` audit check, so the rule-based answer is returned instead.
  Frontend instructions: [HANDOFF_CODEX.md](HANDOFF_CODEX.md).
- With history, references to earlier messages ("Earlier you asked ...") are allowed and
  "What did I ask before?" is answered from the history; without history they are
  rejected and a fixed sentence says that no earlier message is kept. Claims of actions or
  of having no access to the data are always rejected.

Measured through the HTTP API with 4 chats of 5 turns (follow-ups about Crew A in English
and Italian, a topic change and return with MedGemma, a language switch): 20 of 20
answers generative and audited, follow-ups routed to the data, no report in any
conversational turn, MedGemma called only on the 6 biomedical turns. See "Performance".

Every decision is recorded in the response: `generation.question_kind`,
`generation.answer_profile`, `generation.specialist.decision` and `reason`, and a
`model_runs` entry with `role: "specialist"` when MedGemma was really called.

Specialist decisions: `consulted`, `not_configured`, `non_generative`,
`conversational_question`, `general_question`, `factual_question`,
`clinical_advice_question`, `no_physiological_reading`, `no_flagged_result`,
`unavailable`, `failed`.

### Honest limits in conversation

The service is stateless: each request carries one question and no history. So:

- A draft sentence that claims memory ("as I said earlier", "I remember"), an action
  the service cannot take ("I will notify", "I have contacted", reminders, scheduling),
  or a false lack of access ("I don't have access to specific results") fails the
  verifier (`capability_claims` check in the audit), in English and Italian.
- A question that refers to an earlier exchange, sent without history, gets the fixed
  sentence "The assistant keeps no memory of earlier questions. This reply is based on the
  current question and the stored records alone." With history it is answered from it.
- A question about the mission gets "The assistant has no information about the mission
  beyond the stored records of the selected crew member."

## Failure handling

| Situation | Result |
| --- | --- |
| MedGemma not configured | Qwen answer; `decision: not_configured` |
| MedGemma not installed or Ollama cannot serve it | Qwen answer; `decision: unavailable`; fixed sentence "specialist review did not occur" |
| MedGemma times out or returns invalid JSON | Same, `decision: failed`, error type in `reason` |
| Specialist retrieval unavailable (`rag/` missing, packages not installed, admission file missing) | MedGemma reviews on the backend facts alone; `evidence_status: unavailable: <reason>` |
| `rag/knowledge_base` document changed after the review | That document is left out of the index; the others are used |
| MedGemma comment with a value, a diagnosis, a drug or an instruction | Verdict applied, comment withheld (`applied` says so) |
| Qwen unavailable | Rule-based answer (`deterministic_fallback`); MedGemma not called. For a conversational message: a fixed greeting in the operator's language |
| Qwen draft fails verification twice | Rule-based answer; MedGemma not called |
| Response fails its own audit (for example a citation not matching the corpus) | Replaced by the rule-based answer; if that fails too, it is returned with `verification.passed: false` and the failing check named |
| Backend returns records of another crew member | HTTP 502; nothing is explained |
| NASA evidence endpoint absent (404) or failing (5xx, timeout) | `dataset_evidence.status: endpoint_unavailable`; answer otherwise unchanged |
| NASA evidence with synthetic findings, another contract version, crew-telemetry or endorsement flags, a non-NLSP URL or a unit given while marked unresolved | Whole section rejected: `status: rejected` |

## NASA dataset evidence (`orbit_agent/nasa_datasets.py`)

Client of the contract 1.0.0 documented in `docs/nasa-evidence-adapter.md`. The adapter
itself (backend code, tests, schema and docs from commit `cc7c55a` on
`feature/nasa-evidence-adapter`) was merged unchanged into this branch by merge commit
`4a0341e`, so a backend started from this branch serves `/api/v1/nasa-evidence`. It is
not on `main`. The agent adds no second dataset pipeline: it only calls the endpoint.

- Requested only when the question names heart rate, blood pressure or cardiovascular
  terms, or asks for research context ("NASA", "research", "bed rest", "dataset") about
  sleep or actigraphy. At most two topics; one entry per dataset.
- Shown in `dataset_evidence`, never given to Qwen or MedGemma, so a study volunteer
  cannot become a simulated astronaut in generated text.
- Each item keeps `study_context: terrestrial_bed_rest_analogue`, `crew_telemetry: false`,
  `clinically_validated: false`, `nasa_endorsement: false` and the per-variable unit
  status. MR001G units stay `null` / `unresolved`; nothing is inferred.
- The adapter's structural counts (records, cells) are not forwarded.
- When items are shown, fixed sentences say that they describe bed-rest volunteers, not
  this crew member, and that unresolved units allow no comparison.

## Marco's specialist RAG (`rag/`) for MedGemma

Inspected on `origin/main` (`rag/src/assistant/assistant.py`, `crew.py`, `knowledge.py`,
`rag/knowledge_base/`). Nothing in `rag/` was modified.

| Part | Decision | Reason |
| --- | --- | --- |
| Model choice `google/medgemma-1.5-4b-it` | Reused: the same model, official Ollama build `medgemma1.5:4b` | The Hugging Face `transformers` path loads bf16 weights (about 8 GB), which does not fit next to Qwen on an 8 GB GPU; the Ollama Q4_K_M build does |
| Reasoning-block handling (`<unused94>` / `<unused95>`) | Reused (`strip_reasoning`) | Same model behaviour |
| Greedy decoding | Reused (temperature 0, fixed seed) | Reproducible reviews |
| Retrieval (`knowledge.py`: hierarchical BM25 + `BAAI/bge-small-en-v1.5` embeddings, reciprocal rank fusion) | Reused as is, loaded read-only from its file | Marco's own retrieval, not a reimplementation |
| Knowledge base (54 documents) | Reviewed section by section; 18 sections of 10 documents admitted, the rest quarantined | See below |
| `crew.py` and `rag/crew_data` | Not used | A second simulated crew dataset with its own anomaly rule (2 standard deviations from a 30-day plateau); the backend is the only crew authority, so MedGemma gets the backend facts. `rag/crew_data` is not in the repository |
| System prompt (emergency steps, causes, documents on request) | Not used | The monitoring assistant must not give emergency steps, doses or cause lists |

### Admission review (`scripts/review_specialist_kb.py`)

The script reads every document of `rag/knowledge_base/` with the same header and section
rules as `knowledge.py` and writes `orbit_agent/specialist_evidence/admission.json`
(reviewed 2026-11-15): one decision and its reasons per document and per section, with
SHA-256 digests of the file and of each admitted section. The rules are conservative
and lexical; a section is quarantined when any of them applies.

| Rule | Quarantined |
| --- | --- |
| Category `protocol` (emergency procedures) | 31 documents |
| Category `reference-values` (would act as clinical thresholds) | 6 documents |
| Mentions a medication, a drug or a dose | 43 sections |
| Emergency or treatment wording | 38 sections |
| Advice addressed to a crew member | 21 sections |
| Numeric comparison that reads as a threshold | 14 sections |
| Cites a source on a host not in the verified list (for example the governmentattic.org copy of the ISS medical emergency manual, whose redistribution status was not reviewed) | 11 sections |
| Numbered list of steps | 8 sections |
| Written as instructions for an assistant | 6 sections |
| No cited source (provenance unknown) | 6 sections |
| Instruction-like wording found by the corpus sanitizer | 2 sections |

Section counts overlap: a section can meet several rules. Result: 10 knowledge documents
with 18 sections admitted; 44 documents and 70 sections quarantined. All 5 FAQ documents
were quarantined (advice). Admitted sections cite NASA pages, NASA Technical Reports,
PubMed Central, DOI links, the Canadian Space Agency or peer-reviewed journals. Their
subjects: Artemis II health studies, landing loads and spinal deconditioning, the
in-flight measurement limits of bone and muscle loss, short-duration commercial crews,
noise exposure, the Human Research Program risk overview, immune changes, in-flight
medical equipment, nutrition and dehydration, and known sex differences.

The licences of the cited works were not reviewed one by one: the admitted passages are
Marco's own text and are never shown to the operator, only listed by document and
section.

At run time (`orbit_agent/specialist_evidence/knowledge.py`):

- The adapter imports `rag/src/assistant/knowledge.py` by path under a private module
  name and writes the admitted sections only to a temporary folder, which is what
  `knowledge.Index` indexes. Its embedding cache also goes to the temporary folder;
  nothing is written under `rag/`.
- A document whose file digest differs from the review is left out ("file changed after
  the review"); a section is also left out when its digest differs or the corpus
  sanitizer flags it. `python -m scripts.review_specialist_kb --check` fails when the
  knowledge base changed, so a new review is needed before it is used.
- The review query is built from the readings and the facts they cite. At most 2
  passages are given to MedGemma, each with cosine similarity of at least 0.70 to the
  query, cut to 160 words. Measured on the admitted sections: unrelated queries scored at
  most 0.52, Noor's sleep readings at most 0.60, landing and deconditioning queries
  0.75-0.80. No admitted section is about sleep, so sleep reviews usually receive no
  background (`evidence_status: none_relevant`).
- The prompt tells MedGemma that the background describes spaceflight in general, never
  this crew member, is to be used only to judge whether a reading claims more than is
  known, and is never crew data. Its verdict still applies only to the readings, and any
  comment goes through the same verifier as before, so a value from a passage cannot
  reach the answer.
- `generation.specialist.evidence_status` is `used`, `none_relevant`, `not_used` or
  `unavailable: <reason>`; `generation.specialist.evidence` lists document, section,
  sources and similarity of each passage given to MedGemma.
- The index is built once per process (first review or warm-up): 46 s on first use
  including the embedding model download, a few seconds when the model is cached, then
  about 20 ms per query. Packages: `requirements-specialist.txt` (numpy, rank-bm25,
  sentence-transformers, and a CPU build of torch). Without them, or without `rag/`,
  MedGemma reviews on the backend facts alone and the status says why.

## Performance (measured 2026-11-15)

Setup: Windows 11, RTX 4060 8 GB, 32 GB RAM, Ollama 0.40.16, `qwen3.5:4b` and
`medgemma1.5:4b` (both Q4_K_M), backend of this branch seeded with the Mission Demo
Seeder. Times are end to end (backend reads, retrieval, models, verification, audit).
The 95th percentile uses the nearest-rank method; with few runs per class it equals or
nearly equals the maximum. GPU memory in use by other applications changed during the
day and changes the results (see "GPU memory"); each comparison below was run back to
back.

### Latency of the final configuration

`python -m scripts.validate_integration --runs 3`: 15 scenarios x 3 warm runs, after
two cold starts, with the shipped defaults (MedGemma unloaded after each review). The
general class was measured again after its last change (5 scenarios x 3). About 5.0 GB
of the 8 GB GPU memory was in use with Qwen loaded.

| Class | Runs | Median | P95 (nearest rank) | Range |
| --- | --- | --- | --- | --- |
| Conversation (greeting) | 3 | 2.7 s | 4.9 s | 2.7-4.9 s |
| General question | 15 | 4.5 s | 8.0 s | 3.1-8.0 s |
| Brief Qwen answer (factual question) | 3 | 7.4 s | 7.6 s | 7.4-7.6 s |
| Full Qwen answer, no review | 12 | 9.6 s | 10.3 s | 7.0-10.3 s |
| Qwen + MedGemma review | 12 | 18.1 s | 19.9 s | 16.0-19.9 s |

Through the HTTP API (`POST /agent/v1/explanations`) on the final code, after a restart
of the service, about 5.1-5.5 GB of GPU memory in use:

- 17 single English and Italian messages, a first pass and a warm pass: 34 of 34 answers
  generative, 34 audits passed, MedGemma called for the 3 biomedical questions only.
- 4 chats of 5 turns, each request carrying the earlier turns: 20 of 20 generative and
  audited.

| Class (warm) | Single messages: runs, median, range | Chats: runs, median, range |
| --- | --- | --- |
| Conversation (greetings, thanks, platform, memory, off-topic) | 11, 1.4 s, 1.2-3.7 s | 6, 1.4 s, 1.2-3.4 s |
| Brief answer ("How much did Crew A sleep?", "Quanto ha dormito Crew A?", "E rispetto a ieri?") | 2, 6.2 s, 5.6-6.9 s | 5, 6.2 s, 4.2-11.4 s |
| General question | | 1, 7.9 s |
| Full answer without review | 1, 16.5 s (Italian clinical-advice question) | 2, 7.4 s, 6.3-8.4 s |
| Qwen + MedGemma | 3, 19.7 s, 17.8-19.8 s | 6, 18.7 s, 11.3-21.9 s |

- A greeting used to produce a full report (10-18 s with a review); it is now answered
  in about 1-1.5 s.
- Sending the history adds the earlier turns to the prompt (at most 8 x 600 characters);
  the follow-up answers above took as long as single questions of the same class.
- Italian answers are longer in tokens than English ones, so full Italian answers take a
  few seconds more.
- Qwen ran at 64-73 tokens per second when it had the GPU to itself.
- The brief and conversation answers that follow a review include about 2 s to reload
  Qwen: loading MedGemma for a review made Ollama unload Qwen in 13 of 45 runs.
- MedGemma review, including its 3.1 s load: 5.2-6.5 s; 1,232-2,500 prompt tokens (2,500
  with the two `rag/` passages), 108-183 output tokens.
- Specialist retrieval (`rag/` index query): about 20 ms per review once built.
- NASA dataset evidence added 3.5-101 ms per request.
- Rule-based answer with Qwen unreachable: 2.1 s (time to the refused connection).

### Cold start

| First request after unloading both models | Time |
| --- | --- |
| Greeting | 4.9 s (Qwen load 2.0 s) |
| Qwen + MedGemma answer, first review of the process | 31.4 s (Qwen load 2.0 s, MedGemma load 3.1 s, building the `rag/` index with the embedding model) |

The HTTP service loads Qwen and builds the `rag/` index at start-up
(`warm_up_on_start`), so the first operator request pays neither.

### GPU memory

- Qwen alone: 3.1-3.4 GB in GPU memory. MedGemma: 2.7-2.9 GB.
- Whether both fit at once depends on the other applications using the GPU. With about
  4.9 GB in use, keeping MedGemma loaded made Qwen run at about 25 tokens per second
  instead of 55-70, although `ollama ps` still reported both models "100% GPU". Measured
  back to back on the same mixed sequence (greeting, general, review, brief, review):

| MedGemma keep-alive | Qwen-only answers | Qwen + MedGemma, median |
| --- | --- | --- |
| `0`: unloaded after each review (default) | 5.0-7.7 s | 18.4 s (18.0-18.8 s) |
| `10m`: kept loaded | 3.4-30.1 s | 34.5 s (27.0-46.1 s) |

  Earlier in the day, with more free GPU memory, `10m` gave reviews a median of 13.3 s
  (9 runs) without slowing Qwen. Unloading costs about 3-5 s per review and was chosen
  because it never slows the rest of the conversation.
- An external slowdown was also seen once: four consecutive answers at 21-28 tokens per
  second with unchanged drafts, then back to normal.

### MedGemma on the CPU (`specialist_gpu_layers = 0`)

Measured earlier to keep Qwen alone on the GPU: Qwen + MedGemma median 21.6 s, P95
32.7 s (9 runs; MedGemma review 8.4-18.1 s). Slower than unloading MedGemma from the GPU
after each review.

### Against the targets

| Target (engineering goal) | Measured | Status |
| --- | --- | --- |
| Simple Qwen request under 5 s | conversation 1.2-1.5 s; general 4.5 s; brief 5.5-7.4 s | Met for conversation and general questions; brief answers not |
| Dual-model response under 15 s | median 18.1 s (unloading MedGemma); 13.3 s when both fit in GPU memory | Not met with the reliable default |

Options not yet taken: shorter full drafts (output length dominates Qwen time), streaming
the answer to the operator, caching the backend reads between consecutive questions, and
choosing the MedGemma keep-alive from the free GPU memory at run time.

## Quality of the second opinion (observed, not validated)

- Contradiction probe (fair reading vs "this proves severe chronic sleep deprivation"
  on Noor's real facts): MedGemma judged the fair reading `supported` and the
  overstated one `unsupported` in every run (6 of 6 in the first measurement, GPU and
  CPU; 7 of 7 in the runs of this phase).
- In the final run, MedGemma removed one Qwen reading as `unsupported` in 11 of 12
  reviews (two in the bone and muscle reviews, which received `rag/` background). In the
  case inspected earlier the removed reading was self-contradictory ("No physiological
  conclusion is possible because the data quality is acceptable but the trend relies on
  missing nights"), and the removal improved the answer. The other removed readings were
  not inspected one by one.
- Sample: 4 questions about one simulated crew member. This shows the mechanism working;
  it does not show that two models give better answers in general, nor that the `rag/`
  background changes the verdicts.

## Startup

```powershell
# 1. Ollama with both models
ollama pull qwen3.5:4b
ollama pull medgemma1.5:4b          # optional; about 3.3 GB; HAI-DEF terms apply

# 2. Backend (existing commands). This branch includes the NASA evidence adapter; a
#    backend from main reports dataset_evidence.status = endpoint_unavailable.
Set-Location backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
python -m app.demo_seed seed --base-url 'http://127.0.0.1:8000/api/v1'

# 3. Agent with MedGemma as reviewer and its rag/ background retrieval
Set-Location ai_agent
.\.venv\Scripts\Activate.ps1
pip install --index-url https://download.pytorch.org/whl/cpu torch==2.15.0
pip install -r requirements-specialist.txt
python -m scripts.review_specialist_kb --check   # fails if rag/knowledge_base changed
$env:ORBITVITALS_AGENT_SPECIALIST = "medgemma"
uvicorn orbit_agent.api:app --port 8100

# One question from the command line
python -m orbit_agent explain --crew sim-mission-v1-02 --domain sleep `
    --question "Why is Crew B's sleep declining compared with the baseline?" --specialist medgemma

# Live measurements (needs both models and a seeded backend)
python -m scripts.validate_integration --backend-url http://127.0.0.1:8000/api/v1 --runs 3
```

Settings (environment variables `ORBITVITALS_AGENT_*`): `SPECIALIST` (`none` or
`medgemma`), `SPECIALIST_MODEL`, `SPECIALIST_TIMEOUT_SECONDS` (90),
`SPECIALIST_GPU_LAYERS` (-1), `SPECIALIST_KEEP_ALIVE` (0), `SPECIALIST_KNOWLEDGE`
(true), `SPECIALIST_KNOWLEDGE_TOP_K` (2), `SPECIALIST_KNOWLEDGE_MIN_SIMILARITY` (0.70),
`CONVERSATION_MAX_OUTPUT_TOKENS` (200), `GENERAL_MAX_OUTPUT_TOKENS` (800),
`BRIEF_MAX_OUTPUT_TOKENS` (500), `CONVERSATION_MAX_TURNS` (8),
`REPLY_LANGUAGE_DETECTION` (true), `NASA_DATASET_EVIDENCE` (true), `WARM_UP_ON_START`
(true). With `WARM_UP_ON_START` and MedGemma configured, the service also builds the
specialist retrieval index at start-up. MedGemma itself is not preloaded: when GPU memory
is short, loading it would push Qwen out.

## Contract changes for the frontend (schema 0.2.0)

All additive. `schema_version` changed from `0.1.0` to `0.2.0`, so a client that pins
`0.1.0` will reject responses until it updates its schema snapshot
(`ai_agent/schemas/agent_response.schema.json`). 0.2.0 has not been released yet, so the
additions below are part of it.

Request (`ai_agent/schemas/explanation_request.schema.json`), two optional fields. A
client that omits them gets the previous behaviour, so the current dashboard client keeps
working unchanged:

- `conversation`: earlier chat messages, oldest first, at most 40 items:
  `{"role": "operator" | "assistant", "text": string (1-2,000 characters),
  "crew_member_id": string | null, "domain": domain | null}`. To support follow-up
  questions, the dashboard sends the operator's messages and the assistant's `headline` of
  each earlier answer, with the crew member it was about. The agent keeps nothing.
- `language`: `"en"` or `"it"`, to force the reply language (for example from a language
  switch in the interface). Omitted: English, or Italian when the operator writes in or
  asks for Italian.

Response:

- `dataset_evidence` (new, always present): status, topics, reason, items, failures,
  notice.
- `generation.question_kind`: `none`, `greeting`, `general`, `factual`, `interpretive`,
  `clinical_advice`. `generation.answer_profile`: `conversation`, `general`, `brief`,
  `full`.
- `generation.reply_language` (`en` or `it`) and `generation.context_turns` (earlier turns
  used; 0 for a question answered on its own).
- A conversational answer (`answer_profile: "conversation"`) has a headline and nothing
  else: empty observations, readings, evidence, uncertainties and suggested checks, and
  `human_review.recommended: false`. `facts` and `status_summary` are still filled.
- `generation.specialist`: `decision`, `model`, `duration_ms`, `notice`,
  `evidence_status`, `evidence[]` (each: `evidence_id`, `document_id`,
  `document_title`, `section`, `sources`, `similarity`, `knowledge_base`).
- `generation.specialist.decision` gains `conversational_question` and
  `general_question`.
- `generation.model_runs[]` may contain `role: "specialist"`.
- `citations[]`: `source_type`, `authors`, `year`, `license`, `verification_url`
  (from the corpus expansion).
- `verification.checks[]` gains `crew_identity`, `source_attribution` and
  `capability_claims`.
- A greeting answer has no observations and usually no citations or
  `evidence_context`; a client should not assume they are non-empty.

### Files outside `ai_agent/` on this branch

Only the merge of the NASA Dataset Evidence Adapter (`4a0341e`, commit `cc7c55a` by its
owner, unchanged): `backend/app/nasa_evidence/`, `backend/app/api/routes/nasa_evidence.py`,
the router, configuration and `main.py` changes it needs, `backend/tests/nasa_evidence/`,
one line in `backend/tests/api/test_openapi_and_cors.py`, a section of
`backend/README.md`, `backend/scripts/export_nasa_evidence_schema.py`,
`schemas/nasa_evidence.schema.json`, `docs/nasa-evidence-adapter.md`,
`docs/examples/nasa-evidence-synthetic.json` and its section in `docs/api-contracts.md`
(22 files). After the merge the backend tests of the adapter, the API and the
architecture passed (214). No other backend, frontend, shared schema or `rag/` file was
changed.

## Implemented and pending

| Item | State |
| --- | --- |
| Qwen as the only writer, verified sentence by sentence | Implemented |
| Routing: conversation/general/brief/full drafts, specialist decision, all recorded | Implemented and tested live |
| Honest limits: no memory, no actions, no mission data beyond the records | Implemented (verifier check and fixed sentences) |
| Conversation without reports (greetings, platform, small talk, out-of-scope requests) | Implemented and tested live through the HTTP API |
| Replies in English and Italian, Italian verifier word lists | Implemented and tested live; Italian lists are a first, unreviewed version |
| Italian versions of the fixed rule-based sentences of data answers | Pending: still English |
| Multi-turn conversation (history kept by the client, sent in `conversation`) | Implemented and tested live through the HTTP API; the dashboard must send the history (Codex) |
| MedGemma adapter through Ollama, conservative merge, failure reporting | Implemented and tested live |
| Marco's `rag/` retrieval as MedGemma background, admission review, digest pinning | Implemented and tested live; 18 sections admitted |
| 114-entry corpus with retrieval scoring, citation checks, injection screening | Implemented (from `feature/ai-agent-corpus-expansion`) |
| NASA dataset evidence: adapter merged into this branch, client, validation, fixed wording | Implemented and tested live |
| Crew identity check (records, requests, facts, sentences) | Implemented |
| NASA evidence endpoint on `main` | Pending: merged here, not on `main` |
| Frontend client update to schema 0.2.0 | Pending (frontend owner) |
| More `rag/` sections (sleep, FAQ) | Pending a rewrite by the owner without advice, doses or thresholds; the admission script is rerun after any change |
| Licences of the works cited by admitted `rag/` sections | Not reviewed one by one; the passages are not shown to users |
| Single-vs-dual answer quality study | Pending: only the observations above |
