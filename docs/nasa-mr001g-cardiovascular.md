# NASA MR001G Campaign 3 cardiovascular source review and importer

This implementation verifies and imports the **complete 80-file Tilt dataset**
from NASA LSDA/NLSP and computes descriptive statistics on unchanged source
numerical scales. It is a local scientific review pipeline, with **unverified
source units**, rather than a validated canonical cardiovascular measurement or
clinical-evaluation pipeline. Original data and private results are not distributed.

## Exact source and review scope

| Item | Official identity |
| --- | --- |
| Dataset | UTMB Bedrest Campaign 3 Tilt |
| Catalog | `MR001G_Campaign_3_Tilt` |
| Dataset record | `f4a134da-7131-55f8-a0a1-e67d56509432` |
| Experiment | Neuroendocrine and Cardiovascular Response to Tilt (Flight Analog), `MR001G` |
| Experiment record | `09bd2406-b323-5f7c-b0ac-d4585f0015ff` |
| Experiment DOI | [10.83263/gz1q-a824](https://doi.org/10.83263/gz1q-a824) |
| Campaign | UTMB Campaign 3, ground program at the UTMB Flight Analogs Research Unit |
| Mission record | `593a6726-8650-551a-8d67-0f03468de92f` |
| Source processing level | Processed Data |

Official endpoints:

- [Dataset metadata](https://nlsp.nasa.gov/api/v1/data/datasets/f4a134da-7131-55f8-a0a1-e67d56509432/full)
- [Experiment metadata](https://nlsp.nasa.gov/api/v1/data/experiments/09bd2406-b323-5f7c-b0ac-d4585f0015ff/full)
- [Campaign metadata](https://nlsp.nasa.gov/api/v1/data/missions/593a6726-8650-551a-8d67-0f03468de92f/full)
- [Human-readable dataset record](https://nlsp.nasa.gov/search/data/details/f4a134da-7131-55f8-a0a1-e67d56509432?dataType=DATASETS)

The manifest at `data/nasa/utmb_campaign_3_mr001g_tilt/manifest.json` lists every
exact download URL and SHA-256 digest: **80 original CSV files and three full
metadata responses**. All 80 source MD5 values matched NASA file metadata, and the
CSV bodies total 162,290 bytes. The complete cached snapshot totals 1,448,205 bytes.
Original filenames contain participant identifiers; the public manifest publishes
only their SHA-256 fingerprints. Verified original names are available locally in
the downloaded metadata and private report. CSV cache names use opaque file UUIDs.

The MR001G experiment also links eight Campaign 3 hormone datasets, each with
multiple exports. These are outside this importer. A variable list inherited from
the parent experiment is not proof that a particular hormone CSV contains HR/BP.
The review and import scope is the complete named **Tilt** dataset, not all files
from all MR001G campaigns or every hormonal assay in Campaign 3.

## Participants, records and terrestrial context

The 80 files contain **1,868 CSV data records**, of which **45 are entirely empty
comma-delimited source records**. All are retained. There are 26 distinct nonempty
campaign/subject pairs in the source fields and seven observed subcampaign labels:
C3A, C3B, C3C, C3D, C3E, C3G and C3H. No C3F file is inferred or generated.

The broader NASA Campaign 3 narrative describes 52 enrolled volunteers and 23
completers, with 14 men and nine women among completers. Those figures describe
the campaign, not the membership or sex distribution of this 26-identifier export.
Age, sex, individual completion status and participant characteristics are not
established by these CSVs. No demographic join to another experiment is performed.
Identifiers refer to ground-study subjects, not crew members or astronauts in flight.

The campaign used terrestrial head-down bed rest with pre-test, in-test and
recovery testing. The experiment narrative describes supine recordings and upright
tilt, potentially terminated early. Different file lengths and absent follow-ups
must not be interpreted as activity nonadherence, identical exposure, or clinical
deterioration. Source sampling, dropout and protocol exposure are not reconstructed.

## Variables, definitions and unresolved units

Ten header layouts occur. Context columns are `ID`, `Campaign`, `Subject`,
`Test_Phase`, `BR_Day`, `Date`, `Min` or `Minute`, and `Stage`. Other columns include
`AVE SV`, `AVG CO`, `TPR`, optional `Comments` and an `Unnamed: 14` export column.
All decoded source cells are retained locally; auxiliary columns are not given
invented unit definitions or silently dropped. The selected numeric channels are:

| Source column | Source-label interpretation | Canonical candidate | Source unit status |
| --- | --- | --- | --- |
| `SBP` | Systolic pressure candidate | `systolic_blood_pressure`, `mmHg` | Not verified for this export |
| `DBP` | Diastolic pressure candidate | `diastolic_blood_pressure`, `mmHg` | Not verified for this export |
| `HR` | Reported HR; acquisition method unspecified | `heart_rate`, `bpm` | Not verified for this export |
| `HR (Dinamap)` | Source-labeled Dinamap HR | `heart_rate`, `bpm` | Not verified for this export |
| `AVE HR` | Averaged HR; window/channel definition unspecified | `heart_rate`, `bpm` | Not verified for this export |

No dataset-specific ReadMe or unit dictionary was found among the 80 CSVs, linked
protocol/document records, or the public MR001G document search. The latter located
publication listings rather than a release-specific dictionary. The definitions
in this manifest are authored descriptions of source labels, **not a NASA-certified
dictionary**. No canonical unit conversion or normalization is performed.
Every numerical observation and descriptive group explicitly has `unit=null`.

A related primary [NASA NTRS preprint](https://ntrs.nasa.gov/citations/20080010634)
describes Dinamap and Finapres instrumentation in tilt testing and reports
conventional BP/HR units in an earlier, smaller study. It supports context, but
does not verify every column, averaging window or channel in this later export.
Its publication/copyright status does not determine the CSVs' redistribution rights.

`HR`, `HR (Dinamap)` and `AVE HR` remain separate source channels. They are never
substituted or pooled merely because all have a heart-rate candidate interpretation.
Recognizing a label or a finite number is not validation of its unit, calibration,
sensor quality, physiology, clinical meaning or canonical API eligibility.

## Missingness and questionable records

Computed from the complete verified source snapshot:

| Source channel | Finite reported values | Missing cells in a present column | Structurally absent cells |
| --- | ---: | ---: | ---: |
| SBP | 1,795 | 73 | 0 |
| DBP | 1,753 | 83 | 32 |
| HR | 1,621 | 103 | 144 |
| HR (Dinamap) | 111 | 1 | 1,756 |
| AVE HR | 1,405 | 2 | 461 |

There are **6,947 present selected cells**, comprising **6,685 finite values**,
**262 missing cells** and zero invalid numerical cells in those five channels.
Absent columns are recorded as structural coverage gaps; no observation or null
measurement is fabricated for a column that was never present. Empty and `NA`
cells remain explicitly missing; reported zeros are retained as observed numbers.
Nonmissing unparseable/nonfinite or float-unrepresentable values, if encountered,
retain their strings and an `invalid_numeric` status rather than being silently
classified as source missing.
Nonzero values that underflow to floating-point zero are not accepted as reported
zeros. These numeric failures do not occur in the acquired selected channels.

There are 56 rows missing context fields, including the 45 empty rows and **11
nonempty rows**. Missing identities, dates or phases are not filled from filenames,
neighboring records, campaign schedules or another experiment. Unattributed finite
values remain in separate context groups. Original row IDs are absent in 77 rows;
file UUID plus CSV record ordinal supplies provenance without inventing a source ID.

One stage label has trailing whitespace. Only its grouping label is trimmed; the
original cell and an explicit issue remain. One relative-step cell uses `13:44`;
it is retained as a nonnumeric step, not converted to a clock time or decimal minute.
Source dates parse as calendar dates, without time zone or measurement instants.
Eleven rows have dates later than the campaign end stated in the catalog narrative.
These are annotated `date_after_catalog_narrative_end`; the narrative may be stale.
No date is overwritten, clipped, shifted or assigned an invented UTC timestamp.

All **1,753 finite SBP/DBP pairs** were compared directly on their original numeric
scales: **zero have SBP below DBP and zero have equal values**. This does not mean
that all measurements are medically normal or validated. The code checks exact
decimal ordering and, for any inversion, retains both values, emits a source
consistency flag and includes the finite values in transparent unfiltered summaries.
No swap, correction, filtering or clinical threshold is applied.

The previously investigated reversed-pressure table belongs to the distinct
[BRSMCF echocardiography dataset](https://nlsp.nasa.gov/search/data/details/c3bdfa7e-6661-5891-9ba0-0fc7c7a080d6?dataType=DATASETS),
not MR001G Tilt. Its [observation file](https://nlsp.nasa.gov/api/v1/files/e81adbae-0290-5d34-9c31-70d382902a24/download)
was rechecked separately, confirming inverted reported pairs there. No values from
BRSMCF are imported, repaired, or substituted into MR001G. Participant-level review
details and actual pressure values are intentionally absent from this document.

## Computation and reproducibility

The unchanged `app.algorithms.robust_statistics.describe` utility computes the
existing Pydantic `BaselineStatistics` fields: mean, sample standard deviation,
median, unscaled MAD, minimum and maximum. Inputs are finite source numbers parsed
to floats; exact original strings remain available for precision and provenance.
The utility is tested project code, not evidence of clinical validation.

Grouping is by **file UUID, original campaign/subject/phase/bed-rest-day/date
context, stage grouping label, and source variable**. It yields **616 groups**,
including 14 groups without finite values. Missing contexts are not merged into
identified subjects, nor are different channels or experimental stages pooled.
All-missing groups have null statistics; one-value groups have null sample SD.
Numerically unrepresentable results receive an explicit failure status.

All finite values are included, even when source context or paired values are
flagged. Missing/invalid cells alone are excluded from the numeric sequence, with
their counts and raw values retained. No imputation, inferred rows, outlier removal,
medical ranges, established baselines, health scoring, statistical significance,
independence assumptions or causal interpretation is introduced. Repeated records
from a protocol are not independent participants.

Reports include the trusted manifest and digest, file hashes, source columns, raw
cells, CSV ordinals and deterministic observation identifiers. Identifiers include
file identity as well as content hash, so identical bodies under different file
records remain distinct. Original filenames stay in private reports/cache metadata.
Algorithm and adapter code are fingerprinted with LF-normalized code hashes;
scientific files are always hashed as original bytes. No generated clock field is
introduced, so repeated imports of identical verified bytes/code are reproducible.

## Download and run locally

Install the existing backend requirements, then run from `backend` in PowerShell:

```powershell
$mrCache = Join-Path $env:LOCALAPPDATA 'OrbitVitals\nasa\utmb_campaign_3_mr001g_tilt'
python -m app.nasa_mr001g --data-dir $mrCache download
if ($LASTEXITCODE -ne 0) { throw 'MR001G acquisition failed. Stop and inspect the error.' }
python -m app.nasa_mr001g --data-dir $mrCache verify

$mrReport = Join-Path $env:TEMP ('orbitvitals-mr001g-' + [guid]::NewGuid().ToString('N') + '.json')
python -m app.nasa_mr001g --data-dir $mrCache import --output $mrReport
$mrResult = Get-Content -LiteralPath $mrReport -Raw | ConvertFrom-Json
$mrResult.summary | ConvertTo-Json -Depth 8
$mrResult.api_integration | ConvertTo-Json -Depth 5
```

`--summary` omits raw rows from the **private local file** but still includes
subject/context statistics. Do not publish either report variant or its contents
in logs or CI artifacts. The CLI prints only aggregate counts and unit limitations.
No API server is needed; no crew member, canonical measurement, baseline or
cardiovascular evaluation is created. Shared contracts cannot preserve all source
provenance, and neither verified units nor aware timestamps are available here.

New cache/report destinations inside the repository are refused. Existing different
files are never replaced. All source bytes, complete file coverage, metadata
identities, NASA MD5 values and filename digests are verified before a new cache
is written. Existing identical files are reused. `verify` and `import` work offline
after acquisition and trust the checkout manifest rather than a cache-local file.

Acquisition stops on the first network, response, size, checksum or provenance
failure before new source files are written; there is no retry, substitute source
or hidden revision. A later filesystem interruption can leave an incomplete cache,
which verification rejects and the CLI does not report as successful. NASA must
continue to serve the pinned snapshot for a fresh reproduction.
If it changes or becomes unavailable, report the blocker and review the revision;
do not silently relax verification. The existing Actigraphy pipeline is untouched.

## Licensing and publication boundary

Public accessibility is verified and local technical processing was demonstrated.
Neither establishes a general reuse license or redistribution grant. The
[NASA Science Data Licenses policy](https://science.data.nasa.gov/about/license)
does not justify assuming CC0 for every NASA-hosted file. The
[NLSP catalog entry](https://data.nasa.gov/dataset/nasa-life-sciences-portal-nlsp)
does not specify a license. No bundle-specific grant was found in reviewed sources.
The software license does not relicense original CSVs, metadata or derivatives.

Only authored code, synthetic fixtures, this report, the authored notice and factual
provenance belong in Git. All original files, full metadata and participant-level
results remain in external local caches. Redistribution remains **unconfirmed**,
not declared prohibited. Obtain archive clarification for the exact intended reuse,
sharing or publication before changing this boundary. Do not imply NASA endorsement.

## MR080G alternative: documented, not substituted

MR001G acquisition succeeded reliably. Its unresolved export-specific unit dictionary
blocks canonical measurement mapping. The official MR080G **Aerobic Capacity
(Flight Analog)** experiment was therefore also investigated as a possible future
alternative, DOI [10.83263/w056-8t76](https://doi.org/10.83263/w056-8t76).

- [MR080G experiment](https://nlsp.nasa.gov/api/v1/data/experiments/07f12dd0-6725-582c-a4d2-618ed8b8c452/full)
- [Campaign 3 ReadMe collection](https://nlsp.nasa.gov/api/v1/data/datasets/1f0a3780-accf-5cb9-a2ad-791dd0d825d4/full)
- [Verified session-report sample](https://nlsp.nasa.gov/api/v1/files/dd51c146-c0a8-5e60-8d70-af92c79bba41/download): 528 bytes; SHA-256 `2c9bd0a805ab99602a8d41a845b3fc3e1dc842a311813d00a1610b2183ea2dae`.
- [Verified data-entry sample](https://nlsp.nasa.gov/api/v1/files/0bb0d611-c143-560a-b3b1-c14c0ef38cb0/download): 593 bytes; SHA-256 `a76ebcde2a6ac022a2a0815b3d3864c079e47aaf44038772b1e09a609bca3a36`.

Both samples were actually acquired and matched NASA MD5 metadata. The item called
ReadMe is a **participant session report**, with explicit resting HR/BP unit labels
and personal study attributes, not a general dictionary. It remains private. These
unit labels do not verify the entire data-entry collection or MR001G channels.
The full MR080G corpus is not validated or implemented here. No MR080G observations,
demographics or physiological values are copied into the MR001G analysis or Git.

## Tests, limitations and scientific handoff

Normal automated tests use invented `SYNTHETIC_*` cohorts and `TEST_PERSON_*`
subjects, future test dates, artificial pressure inversions, zeros, missing fields,
invalid numeric/time cells and deliberately incomplete layouts. Fixtures are Python
constructors, not copied NASA files. They retain `is_synthetic=true`; production
manifest validation rejects their identity. Network access and real default caches
are blocked in these tests. All generated fixture payloads/digests are test-only.

Tests exercise complete source retention, distinct channels, exact decimal anomaly
checks, missing/invalid/absent distinctions, null units, no context imputation,
source-date discrepancies, padding, real utility invocation, Pydantic statistics,
repeatability, strict catalog coverage, hashes, filenames, external destinations,
private CLI output and first-failure acquisition stops without partial writes.

Scientific review questions for Marco, coordinated through the project owner:

1. Obtain an authoritative unit/channel/averaging dictionary for this exact release.
   Related-paper units and MR080G labels are insufficient substitutes.
2. Reconcile source dates after the catalog narrative end, incomplete context,
   absent row IDs, nonnumeric relative steps and the one incomplete column layout.
3. Review whether any source notes, protocol variants or missing follow-ups justify
   a separately documented analysis policy. This importer silently excludes none.
4. Verify the separate BRSMCF label problem with the archive; do not transfer a
   correction or finding to MR001G.
5. Clarify reuse/redistribution rights before sharing originals or individual
   derivatives. Code-only publication is separate from scientific/API readiness.

Canonical ingestion remains blocked by the source dictionary and temporal/context
contract gaps. Descriptive source-scale review is reproducible; no clinical or
in-flight monitoring claim follows from it. Existing scientific algorithms, shared
schemas/contracts, Actigraphy, frontend and AI-agent code are unchanged.

## Verification completed on 2026-11-15

Run these checks from `backend`:

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m scripts.export_schemas --check
```

- Full backend suite: **1,002 passed** (919 existing cases and 83 MR001G cases).
- Ruff: all checks passed; formatting: 137 files already formatted.
- Exported schemas: up to date; no contract changes.
- Fresh production CLI acquisition: all 83 pinned source files downloaded from
  NASA, with SHA-256, MD5, size and metadata/file linkage verified.
- Independent byte/CSV review: all 1,868 raw row dictionaries and 6,685 finite
  selected values match the originals; all 262 missing cells are preserved.
  Repeated final-code imports produced identical private reports.
- Existing Actigraphy CLI regression with verified original inputs: 207 rows,
  380 observed values, 34 missing values and 18 computed groups.
- Language review covered 180 repository text files, including 134 parsed Python
  files. No Italian code, comments or technical documentation were identified.
  Original scientific source strings are preserved without translation.
- Publication review: 14 new authored files, no existing files modified, no
  original source bodies or participant-level JSON exports in the proposed files.
  The reachable base history audit checked 28 commits, 27 root trees and 191 file
  blobs without excluded source material. Local finalization includes only the
  publication-safe code, synthetic tests, factual manifest and authored English
  documentation. Original files and private results remain outside Git; no push
  or merge is performed.
- Git base: `85932c58b3389c21d0b98f6448840bb099fdb499`, the fetched `origin/main`
  when the clean feature branch was created. Concurrent work later advanced the
  shared `origin/main` reference by two AI-agent commits to
  `891c726ff951eeb516dd7f5e7effdb9a5cba6fb3`. Those changes are not merged here;
  this work does not alter the other agent's files or rewrite branch history.
