# Reproducible NASA actigraphy analysis without redistributing source files

This branch distributes a local importer, CLI, synthetic tests and factual source
provenance. Users download scientific files directly from NASA into their own local
cache. No authentic CSV, original NASA ReadMe, full catalog JSON, individual source
records, or subject-level computed results belong in the publishable history.

The source is **UTMB Bedrest Campaign 1 Actigraphy**, catalog
`BRSMACT_Campaign_1_Actigraphy`, experiment `BRSMAct`, archived by NASA LSDA/NLSP.
The experiment DOI is [10.83263/v7n1-ht75](https://doi.org/10.83263/v7n1-ht75).
These are processed observations from human ground-study volunteers in a
terrestrial bed-rest analog. They are not measurements of astronauts in flight.

## Rights and distribution boundary

Three different questions have different evidence:

| Question | Established evidence |
| --- | --- |
| Public accessibility | Official file endpoints returned HTTP 200 without credentials. Files matched the NASA MD5 values and the acquisition SHA-256 digests. |
| Local processing | The importer can verify and process those files locally. Technical feasibility does not establish a blanket license for every use. |
| Redistribution | Not confirmed for this particular bundle. No file-specific license or grant was found in the inspected sources. |

The official [NLSP catalog entry](https://data.nasa.gov/dataset/nasa-life-sciences-portal-nlsp)
labels the portal license as unspecified. The
[NASA Science Data Licenses policy](https://science.data.nasa.gov/about/license)
distinguishes explicit licenses, its CC0 rule for NASA-led mission data unless
otherwise marked, and other data whose original-source rights need verification.
The source metadata does not establish that this bundle falls under the CC0 rule.
Ground-study status alone neither proves nor disproves its applicability.

The [dataset metadata](https://nlsp.nasa.gov/api/v1/data/datasets/e26501eb-7d7a-5012-8c8e-c5bdb3eecaf6/full)
and original ReadMe were inspected for rights information. The
[OSDR terms](https://science.nasa.gov/reference/osdr-help-terms-and-conditions/)
refer to OSDR-acquired data; they are not automatically a license for this separate
LSDA/NLSP bundle. The repository software license does not relicense downloaded
scientific material. Archive clarification is needed before redistributing the
originals, individual excerpts, or subject-level derivatives.

Only the manifest in `data/nasa/utmb_campaign_1_actigraphy/` is distributed, along
with an OrbitVitals-authored notice and Git attributes. The manifest lists:

| Separately downloaded file | Purpose |
| --- | --- |
| `BRSMACT_Campagin_1_Actigraphy.csv` | Primary individual processed table |
| `BRSMACT_Campagin_1_Actigraphy_Query_Result.csv` | Auxiliary query export; retained locally, not merged |
| `BRSMACT_Campaign_1_Actigraphy_ReadMe.txt` | Original unit/file documentation |
| `dataset.full.json` | Locally named complete catalog API snapshot |

NASA's spelling `Campagin` is preserved. The manifest includes original file IDs,
official HTTPS URLs, byte counts, SHA-256 digests and NASA MD5 digests. Its snapshot
retrieval dates refer to the original source verification; copying the manifest
does not claim a new retrieval date.

## Reproduce from a new checkout

Use Python 3.11 and install the backend development requirements as described in
`backend/README.md`. None of the normal tests require NASA data or network access.
The default cache is outside the checkout, under `%LOCALAPPDATA%\OrbitVitals\nasa`
on Windows or `~/.cache/OrbitVitals/nasa` when `LOCALAPPDATA` is absent.

From your clone's `backend` directory, use Windows PowerShell:

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m scripts.export_schemas --check

$nasaDir = Join-Path $env:LOCALAPPDATA 'OrbitVitals\nasa\utmb_campaign_1_actigraphy'
python -m app.nasa_data --data-dir $nasaDir download
python -m app.nasa_data --data-dir $nasaDir verify

$nasaReport = Join-Path $env:TEMP ('orbitvitals-nasa-' + [guid]::NewGuid().ToString('N') + '.json')
python -m app.nasa_data --data-dir $nasaDir import --output $nasaReport
$nasaResult = Get-Content -LiteralPath $nasaReport -Raw | ConvertFrom-Json
$nasaResult.summary
$nasaResult.descriptive_statistics | Select-Object subject_id, source_phase, metric, observed_value_count, missing_value_count, statistics | Format-List
```

The last two commands inspect private local results. Do not publish their output
or upload that report as a public CI artifact while redistribution remains
unconfirmed. For a smaller **local file**, use `import --summary --output PATH`;
this still contains subject-level statistics and requires an external destination.

The CLI prints file verification status or aggregate record/value/group counts.
It does not print individual observations or per-subject statistics. `import`
requires an explicit output filename. New downloads and reports inside the
checkout are refused, including symlinks that resolve back into it. Reports use
exclusive creation; existing different source files or manifests are never replaced.

The downloader checks all responses and the catalog's file identities, original
names, digests, sizes and ground-study context before writing a cache. It accepts
only the reviewed official HTTPS endpoints and checks final response host/scheme.
Downloads are bounded to the expected file size plus one byte. Existing identical
files are reused, so repeating a download is idempotent. `verify` and `import`
are offline after acquisition, and trust the checkout manifest rather than a
cache-local replacement. Missing files fail explicitly instead of generating data.

Upstream changes, unavailable URLs or revised catalog bytes cause a clear failure.
Do not silently replace the trusted digests. Review and document the new source
version first. Reproduction depends on NASA continuing to serve the pinned files;
this project does not operate a mirror or promise permanent upstream availability.

For a clean demonstration download without reusing any existing cache:

```powershell
$freshNasaDir = Join-Path $env:TEMP ('orbitvitals-nasa-source-' + [guid]::NewGuid().ToString('N'))
python -m app.nasa_data download --output-dir $freshNasaDir
python -m app.nasa_data --data-dir $freshNasaDir verify
```

## Normalization and actual scientific computation

The primary CSV supplies `ID`, `Subject`, `Test_Phase`, `BR_Day`, `Date`, sleep
latency, sleep duration, sleep efficiency and notes. Individual records remain
separate from cohort summaries. The full decoded source cells are preserved only
in the private local report, with source file hash, column and CSV data record
number. The auxiliary query export has a different layout and may contain multiple
records per subject/date; it is never appended or automatically reconciled.

| Source representation | Canonical metric | Unit | Transformation |
| --- | --- | --- | --- |
| Duration `HH:mm` or `HH:mm:ss` | `sleep_duration` | `min` | `60 * hours + minutes + seconds / 60` |
| Efficiency in percent | `sleep_efficiency` | `%` | Identity |

The duration heading says `(hours)`, but the inspected cells use duration syntax
and the source ReadMe specifies `HH:mm`. Decimal-hour strings are rejected.
As an explicitly **synthetic arithmetic example**, `1:17:30` converts to 77.5 minutes.
This example is not a NASA observation. Rational arithmetic avoids truncating
seconds. The documented 0–100 percent bound is a unit constraint, not a medical
threshold. Sleep latency has no canonical metric and remains unmodified source
context; it is not reinterpreted as sleep duration.

Calendar dates use the observed `M/D/YYYY` layout. No clock times, time zones,
sleep-onset/end instants, or observation intervals are inferred. Source bed-rest
phases and day strings remain unchanged; pre-test day signs are not reconstructed.
Missing metric cells remain null, observed zeros remain zeros, absent rows are not
created, and malformed nonmissing values fail validation. Missingness does not
establish a sensor failure. Quality remains unassessed; notes and potential
confounders are retained locally without silent exclusion.

The adapter invokes the existing, unchanged
`app.algorithms.robust_statistics.describe` separately for each subject, bed-rest
phase and metric. It returns the existing Pydantic `BaselineStatistics` fields:
mean, sample standard deviation, median, unscaled MAD, minimum and maximum.
Only missing cells are excluded. All-missing groups have null statistics; a single
value has null sample standard deviation. There is no imputation, outlier removal,
threshold classification, target comparison, established baseline, or clinical
assessment. Authentic results are computed on demand, never stored as fixtures.

The pinned table has 207 rows and yields 380 observed canonical metric values,
34 missing metric cells and 18 descriptive groups. These are aggregate file-shape
checks, not hard-coded per-subject results. A reproduction run computes the counts
and statistics from the downloaded bytes. Reports embed the factual manifest and
its digest, and fingerprint the adapter and existing algorithm with LF-normalized
code digests. Scientific files are always hashed as original bytes. Identical
bytes and code yield identical reports without generated wall-clock fields.

## API and scientific limitations

The current measurement contract requires an aware timestamp and cannot preserve
date-only precision, study provenance and context, original missing cells, or all
source notes. External local storage preserves provenance but does not supply
missing temporal detail. The importer therefore creates no API measurements or
crew members, performs no HTTP ingestion, and does not call baseline/evaluation
endpoints. Bed rest is not relabeled as an in-flight mission phase.

Shared schemas, API contracts, existing scientific algorithms, sleep/vitals modules
and frontend files are unchanged. The scientific contribution remains a verified
normalization and descriptive-analysis proof for a small ground study, without
astronaut reference ranges, mission thresholds, clinical validation, or NASA
endorsement. No unsupported exercise or cardiovascular measurements are fabricated.

## Offline tests and authentic reproduction

All normal NASA-adapter tests use visibly invented `SYNTHETIC_*` subjects, future
test dates, test-only notes and freshly generated fixture digests. Fixtures are
Python constructors rather than copied source CSV/JSON files. Synthetic fixture
reports retain `is_synthetic=true` and an explicit test notice. Production manifest
loading rejects the synthetic fixture identity; test transport injection does not
relax that validation. No real observations are relabeled as synthetic test data.

The test suite blocks NASA network access and does not use a developer's real
default cache. It covers units, original cell preservation, calendar precision,
missing/zero/partial data, malformed/duplicate records, notes, phase separation,
actual algorithm invocation, Pydantic compatibility, deterministic reports,
digest/catalog linkage, path confinement, external destinations, bounded download
failures, idempotency and refusal to overwrite. A genuine reproduction is an
explicit local operation using the commands above, separate from offline tests.
Do not run authentic-data tests with public logs or upload local cache/report files.

## Publishable Git history

This branch starts from `origin/main`, without the archival data commit in its
ancestry. The original private branch remains local, along with its original files
in an ignored private archive. The archival branch is not merged or cherry-picked.
Only the recovered code, newly authored synthetic tests, factual manifest and
authored documentation are included here. Ignoring a file or deleting it in a
later commit would not remove it from earlier commits; that is why this history
was built separately.

Run the read-only audit from `backend`:

```powershell
python -m scripts.audit_nasa_history --ref feature/nasa-data-proof-public
```

The audit requires a complete repository history and refuses shallow clones. It
walks **every reachable commit**, every unique historical root tree and
every unique file blob. It checks excluded source/cache/export paths, CSV files,
the SHA-256 digests of all four original source bodies, and recognizable authentic
report/catalog/excerpt JSON structures. Data removed at the tip still fails.
Tests demonstrate detection of deleted data, renamed original bytes and the same
blob appearing under both allowed and forbidden historical names, using temporary
bare repositories with invented bytes and no additional worktrees.

The audit covers reachable published content, not unrelated private branch objects
in the same local Git database, and is not a general detector for arbitrary data
obfuscation. All newly authored files also require source review. Public history
must be selected explicitly; do not publish private archival refs or use a mirror
of the shared local Git database. No push or merge is part of this task.

## Verification record

Checks were performed with Python 3.11.9, pytest 9.2.0 and Ruff 0.17.5:

| Check | Result |
| --- | --- |
| Complete pytest suite | 919 passed, including 106 offline NASA-adapter/history tests |
| Ruff lint | Passed |
| Ruff formatting | Passed; 127 files already formatted |
| Shared schema freshness | Passed; no contract/schema changes |
| Authored text language review | No Italian identified; code, comments, tests and technical documentation are in English |
| Isolated reproduction | A new source-file-free checkout downloaded four files directly from NASA and verified their pinned digests |
| Repeatability | Two independently written private reports were byte-identical; descriptive statistics matched the preserved original analysis |
| History-audit negative control | The local archival history containing originals was rejected |

The isolated reproduction used a new external cache and checked that the Python
modules loaded from the isolated checkout. Missing data failed before download;
no developer cache, bundled observation file, or stored scientific result supplied
the analysis. Only aggregate file-shape counts are recorded here. No original data,
private report, individual excerpt or per-subject statistic is a public artifact.
Run the history command on the final commit to obtain its exact commit/tree/blob
counts and audit result. Language review combines lexical checks, Python parsing,
token inspection and source review; it is not a formal natural-language proof.

## Questions for scientific review

Coordinate with Marco through the project owner. Confirm the meaning of source
dates, bed-rest day conventions and whether authoritative interval/time-zone
records exist; review duration notation and the auxiliary query reconciliation;
assess the implications of source notes, study protocol and cohort size before
any interpretation beyond descriptive statistics. Separately, request explicit
archive clarification on original and derivative redistribution before changing
this publication boundary. No scientific algorithm is modified to fit missing
source information.
