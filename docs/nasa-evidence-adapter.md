# NASA Dataset Evidence Adapter

Contract version: **1.0.0**. This is a read-only context service for the two existing
NASA pipelines. It is independent of Qwen, MedGemma, the agent corpus and the crew
repository. No dataset replaces simulated Crew A/B/C telemetry or supplies a
dashboard chart, personal baseline, health evaluation or clinical reference range.

## Reviewed sources and supported evidence

| Dataset ID | Source and population | Evidence scope |
| --- | --- | --- |
| `nasa-lsda-brsmact-utmb-campaign-1` | [UTMB Bedrest Campaign 1 Actigraphy](https://nlsp.nasa.gov/search/data/details/e26501eb-7d7a-5012-8c8e-c5bdb3eecaf6?dataType=DATASETS); human ground-study volunteers | Processed sleep duration and efficiency, documented representations, temporal limitations and complete-export validation diagnostics |
| `nasa-lsda-mr001g-utmb-campaign-3-tilt` | [UTMB Bedrest Campaign 3 Tilt](https://nlsp.nasa.gov/search/data/details/f4a134da-7131-55f8-a0a1-e67d56509432?dataType=DATASETS); human ground-study volunteers | Tilt/supine protocol context, separate HR/BP channels, unresolved units and complete-export validation diagnostics |

These populations are not monitored synthetic astronauts or in-flight crews.
The adapter supplies no participant identities, participant counts, demographics,
individual dates, notes, values, pressure pairs or physiological statistics.
Campaign-level enrollment figures cannot establish membership of an export.

The closed catalog in `backend/app/nasa_evidence/catalog.py` routes exact topic tags:

| `topic` | Dataset | Relevant variables |
| --- | --- | --- |
| `sleep` | Actigraphy | Sleep duration, sleep efficiency |
| `actigraphy` | Actigraphy | Sleep duration, sleep efficiency |
| `heart_rate` | MR001G | `HR`, `HR (Dinamap)`, `AVE HR`, kept separate |
| `blood_pressure` | MR001G | `SBP`, `DBP` |
| `cardiovascular_adaptation` | MR001G | All selected HR/BP channels; protocol context only |
| `data_quality` | Both | All selected variables and their validation limitations |

Retrieval has no language-model ranking, embeddings, fuzzy matching or free-text
queries. Dataset order is stable. Identical inputs, source bytes and pipeline code
produce identical response bytes and content-derived evidence IDs. Topic tags are
engineering routing choices, not proof of causality or a NASA scientific taxonomy.

## Publication boundary and numerical policy

The default service reads only the two reviewed public provenance manifests.
It returns authored context and limitations with `source_verification.state` set
to `not_configured`. It does not inspect a developer's default cache or claim that
NASA files were downloaded or reverified during that request.

An operator can explicitly configure external local caches. The adapter then runs
the existing importers, including SHA-256, MD5, byte-count and catalog-linkage
checks. Original bytes and algorithms are unchanged. Importers calculate their
normal private reports in memory; the adapter projects a small whitelist of
whole-export structural counts and discards the private report from its response.
It never writes a report, downloads a file, calls an ingestion endpoint or updates
crew resources. Every request repeats source verification; failures never reuse
previous successful counts. HTTP responses specify `Cache-Control: no-store`.

The only empirical numeric findings exposed are:

| Code | Meaning |
| --- | --- |
| `source_records` | Parsed CSV data records in the selected primary export; MR001G includes comma-delimited empty records |
| `observed_metric_cells` | Observed/finite cells in the importer's selected metric columns; reported zeros remain observed |
| `source_missing_metric_cells` | Explicit blank/NA cells in columns actually present |
| `invalid_numeric_metric_cells` | MR001G nonmissing values that cannot be represented as valid finite numbers |
| `empty_source_records` | MR001G entirely empty comma-delimited records |
| `records_with_missing_context` | MR001G records carrying missing-context issues, including empty records |

Every count carries `scope=complete_selected_export`, the exact
`included_source_columns`, its count unit, data origin and pipeline summary key.
**Topic filtering changes relevant variables, not the scope of these counts.**
MR001G HR queries therefore still identify all five columns counted by the
pipeline. Structurally absent columns are never fabricated as missing cells.
Counts are validation facts, not physiological comparisons, quality scores,
sampling-completeness estimates, sensor-failure diagnoses or independent samples.

Provenance also includes the reviewed manifest's expected file count and hashes.
Those describe the reviewed snapshot even without a local cache; they do not mean
that the sources passed verification on this machine. No physiological mean,
median, range, group result, participant count or measurement value is published.

Public accessibility, successful processing and redistribution permission remain
different questions. Both manifests record redistribution as **unconfirmed**.
This adapter does not assume CC0, establish a new data license or authorize broader
sharing of the originals or derivatives. Its narrow output consists of authored
context, factual provenance and reproducible file-structure diagnostics already
used by the importers' aggregate CLI summaries. Archive clarification is still
needed before expanding that boundary. Do not redistribute private reports or
present the software license as a NASA dataset license. See the source-specific
[Actigraphy](nasa-data-proof-public.md) and [MR001G](nasa-mr001g-cardiovascular.md)
reviews and the [NASA policy](https://science.data.nasa.gov/about/license).

## MR001G unit and interpretation limits

Every MR001G variable has `unit_verification=unresolved`, `canonical_unit=null`
and no normalization. Both Pydantic validation and the JSON Schema enforce the
unit boundary. Related papers or another experiment's labels are not substitutes
for this export's missing unit/channel/averaging dictionary. No quantitative
clinical comparison is permitted until units and protocol are established.

The adapter exposes no pressure values, inversion counts or physiological
adaptation magnitude. The existing importer continues to preserve and annotate
questionable pairs without correction, swapping or removal. Calendar dates and
relative steps do not supply aware measurement timestamps. Missing follow-ups,
source context gaps and catalog date discrepancies remain limitations. A ground
tilt protocol does not establish a direction or magnitude of spaceflight adaptation.

Actigraphy duration conversion remains the existing documented HH:mm[:ss]-to-
minutes conversion. The heading alone must not be read as decimal hours. Sleep
latency is not promoted to a supported metric. Missingness never establishes a
sensor failure, and this adapter does not invoke the Data Quality engine.

## HTTP and Python interfaces

The additive endpoint is:

```text
GET /api/v1/nasa-evidence?topic=heart_rate
GET /api/v1/nasa-evidence?topic=data_quality&dataset_id=nasa-lsda-mr001g-utmb-campaign-3-tilt
```

`topic` is required. `dataset_id` is optional and accepts only the two IDs above.
Invalid enum values or a missing topic return the existing HTTP 422 error shape.
Write methods return 405. No request parameter accepts a path, arbitrary URL,
participant selector, fixture mode or source-revision approval.

Valid requests return HTTP 200 and the versioned `EvidenceResponse`, even when
evidence is incomplete. This lets an agent distinguish an explained evidence
failure from a transport failure without parsing exception text.

| Field | Contract |
| --- | --- |
| `contract_version` | Exact supported version, currently `1.0.0` |
| `topic` | Validated requested topic |
| `status` | `ok`, `partial`, `unavailable`, or `no_matching_evidence` |
| `contains_synthetic_findings` | True only for injected test fixtures; production clients must reject such findings |
| `items` | Ordered dataset evidence, with identity, population, relevant variables, context, provenance, limitations and optional structural findings |
| `failures` | Ordered dataset-specific failure codes and fixed safe explanations; no private paths or source cells |
| `notice` | Mandatory separation from crew telemetry and clinical assessment |

Each item explicitly sets `evidence_scope=scientific_context_only`,
`crew_telemetry=false`, `clinically_validated=false`, `nasa_endorsement=false`
and `redistribution_status=unconfirmed`. Unknown model fields are forbidden.

The complete machine-readable contract is
[`schemas/nasa_evidence.schema.json`](../schemas/nasa_evidence.schema.json),
generated from `backend/app/nasa_evidence/models.py`. It is additive and does not
change the existing shared crew schemas. OpenAPI includes the same response model.
Pydantic also enforces cross-field consistency, topic agreement, synthetic origin,
unique dataset items and response-status semantics.

```python
from app.nasa_evidence import EvidenceTopic, NasaEvidenceAdapter, encode_response

adapter = NasaEvidenceAdapter()  # Reviewed context only; no implicit local cache.
response = adapter.retrieve(EvidenceTopic.HEART_RATE)
print(encode_response(response))
```

Failure codes are `manifest_unavailable`, `manifest_rejected`, `source_missing`,
`source_unreadable`, `source_rejected` and `processing_failed`. Missing/rejected
manifests withhold that dataset entirely. Source failures retain reviewed metadata
but withhold all recomputed findings. `partial` means some reviewed context remains
available alongside failures; `unavailable` means no items could be returned.
An incompatible topic/dataset pair gives `no_matching_evidence` with empty lists.
No source errors, private paths, record contents or tracebacks enter this contract.

Source states are `not_configured`, `verified`, `synthetic_fixture_verified`,
`unavailable` and `rejected`. Only verified states permit numeric findings. The
synthetic state exists for isolated tests and cannot be enabled through HTTP,
environment settings or the production CLI.

`verified` establishes pinned-byte integrity and successful pipeline processing.
It does not resolve MR001G units, validate instrument calibration or imply clinical
or NASA validation. The per-variable unit status and scientific limitations still apply.

## Claude Code handoff to the AI agent

No change to `ai_agent/` or its corpus is included. Claude can add a separate
GET-only client method against the endpoint above in a future agent task.

1. Map the physiological topic to an exact supported tag. Keep backend measurements,
   evaluations and baselines as the authority on the simulated crew observation.
2. Read the endpoint with a bounded timeout. Validate the contract version and
   schema; apply the documented cross-field checks or parse `EvidenceResponse`.
3. Handle non-200 responses as transport/input failures. Handle contract failure
   states explicitly; never substitute generated evidence when NASA context fails.
4. Discard synthetic-fixture findings. Treat `not_configured` as reviewed context
   only, not current source-file verification. Source failures provide no numeric
   support even when metadata remains available.
5. Attach the returned evidence ID, dataset title and NASA URL as an explicit
   ground-analogue citation. Include the relevant limitations with the explanation.
6. Keep dataset context separate from crew facts. Never turn structural counts into
   physiological reference ranges, chart points, clinical classifications or NASA
   validation claims. Never normalize MR001G units or pool its HR channels.

For example: "This NASA-archived ground-study export provides tilt-protocol context;
its HR channel units and averaging definitions remain unresolved. It does not
establish a quantitative comparison with this simulated crew member."

This example is explanatory wording, not a medical assessment or a derived finding.

## Run and reproduce

From `backend`, with the existing development requirements installed:

```powershell
python -m app.nasa_evidence --topic sleep
python -m app.nasa_evidence --topic heart_rate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# In another PowerShell terminal:
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/nasa-evidence?topic=data_quality'
```

To opt in to existing verified external caches before starting the server:

```powershell
$env:ORBITVITALS_NASA_ACTIGRAPHY_CACHE = Join-Path $env:LOCALAPPDATA 'OrbitVitals\nasa\utmb_campaign_1_actigraphy'
$env:ORBITVITALS_NASA_MR001G_CACHE = Join-Path $env:LOCALAPPDATA 'OrbitVitals\nasa\utmb_campaign_3_mr001g_tilt'
```

Acquire those originals separately with the documented existing importer commands.
The evidence adapter never downloads or repairs them. New cache revisions fail
closed; updating a reviewed manifest or its pin requires scientific review.
Do not configure repository-internal caches. No cache is implicitly enabled by
these defaults. The local evidence CLI also accepts explicit `--actigraphy-cache`
and `--mr001g-cache` paths and returns exit code 2 on explained evidence failures.

The entirely synthetic example is
[`docs/examples/nasa-evidence-synthetic.json`](examples/nasa-evidence-synthetic.json).
It reuses the existing invented NASA-parser fixtures and runs the real integrity
checks and importers. Its numeric counts are not NASA findings. Reproduce it with:

```powershell
python -m tests.nasa_evidence.example
```

Only the fixture manifests are injected at the trusted test boundary. The
production catalog's exact manifest pins, source identities and synthetic flag
checks are not relaxed. Example hashes refer to generated test manifests; their
provenance paths point to the fixture constructors rather than real source files.

Verification commands:

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m scripts.export_schemas --check
python -m scripts.export_nasa_evidence_schema --check
python -m scripts.audit_nasa_history
```

The existing NASA history audit remains unchanged, including its exact-digest
synthetic submission-evidence exception. Full publication review must additionally
pass both source manifests to `audit_history` and inspect staged files. No source
CSV, original ReadMe, downloaded metadata, local cache or participant-level report
belongs in this branch. Synthetic fixtures require no NASA access in automated tests.

## Verification record

Verified on 2026-11-15 from base `ae0c781494e19913ce355d21637802365cb295ef`:

- Complete backend suite: **1,075 passed**, including 59 evidence-adapter cases.
- Ruff passed; formatting check: 150 Python files already formatted.
- Existing shared schemas and the additive evidence schema both passed verification.
- The existing NASA history audit passed without changes to its implementation.
  The base history contains 33 reachable commits and 285 distinct file blobs.
- Explicit local HTTP checks verified all 87 pinned source files, returned identical
  repeated responses and preserved original bytes. Actigraphy diagnostics recomputed
  207 rows, 380 observed cells and 34 missing cells. MR001G diagnostics recomputed
  1,868 rows, 6,685 observed cells, 262 missing cells, no invalid selected numeric
  cells, 45 empty records and 56 records with missing context. These are structural
  checks, not physiological comparisons; no participant-level report was published.
- MR001G unit status stayed unresolved, and the HTTP checks created no crew records.
  Automated tests also preserve an existing nonempty simulated crew measurement list.
- Synthetic examples passed exact reproducibility, Pydantic and Draft 2020-12
  validation. Regression tests reject missing verification proof, synthetic-origin
  mislabeling, unsupported MR001G unit normalization and unverified numeric findings.

The local commit is limited to backend integration, authored documentation, the
additive schema and synthetic tests/examples. Shared algorithms, importers,
manifests, crew schemas, Git history audit, AI agent and frontend are unchanged.
No push or merge is part of this task.
