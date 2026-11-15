# Submission evidence and verification record

Review date: **2026-11-15**. Source commit: `036df20`, branch
`feature/frontend-bridge`, in the existing `OrbitVitals-Codex` worktree. The working
tree was clean before this documentation task. Earlier integration work was already
committed when this task began; it has not been reset, discarded or modified here.

## Captured scientific evidence

The [capture script](capture-evidence.mjs) starts the existing private FastAPI test
server on an ephemeral loopback port, runs the real mission seeder, reads the real
resource collections through the verified bridge and checks each stored evaluation
against the seeder's actual output. It stops only its owned API process. Port 8000
is rejected. It does not ingest into or restart the shared service.

Files under [evidence/](evidence/) contain actual Noor sleep responses with existing
`items` envelopes and unchanged contract fields. A separate capture manifest records
settings and hashes. These files are **SIMULATED DATA**, not astronaut records,
clinical validation, new API contracts or fabricated algorithm responses.

| Actual resource collection | Measurements | Baselines | Evaluations |
| -------------------------- | ------------ | --------- | ----------- |
| Vega / `sim-mission-v1-01` | 188          | 7         | 4           |
| Noor / `sim-mission-v1-02` | 171          | 7         | 5           |
| Chen / `sim-mission-v1-03` | 139          | 7         | 4           |
| Total                      | 498          | 21        | 13          |

| Noor checkpoint | Stored evaluation ID                   | Actual result       |
| --------------- | -------------------------------------- | ------------------- |
| 2 nights        | `21aa712c-e1d1-5697-8209-f1949e219cec` | `insufficient_data` |
| 5 nights        | `4614322e-a935-5499-847d-86d627d3194d` | `attention`         |
| 9 nights        | `e7a80a5d-1cef-5e85-8533-641ff2a1294f` | `attention`         |

The selected duration baseline is
`544f923a-eb02-52a0-83bf-7b177b3570f9`. IDs are shown for traceability; clients must
not parse them. The stored reference median is 480 min and sample count 14.
Night counts are 2/2, 4/5 and 7/9; duration medians are 482.5, 460 and 430 min.
The nine-night record ends on October 21 at noon UTC. The observation calendar is
October, unlike the earlier standalone November scenario in `docs/demo/`.

The test server has no expected sleep cadence or sensor ranges configured. Noor's
captured per-metric quality is `acceptable` and completeness is null. Sleep coverage
and missing nights remain in the explanation. This is intentionally not rewritten
to match older cadence-configured quality examples.

## Reproduce and validate

Use the existing Python 3.11 environment with backend development requirements and
Node.js 24. Install the existing bridge/frontend locked dependencies if needed.
From the repository root:

```powershell
$env:ORBITVITALS_PYTHON = (Get-Command python).Source
npm --prefix integrations/frontend-bridge run build
node --experimental-strip-types docs/submission-2026/capture-evidence.mjs
python docs/submission-2026/verify_package.py
```

The optional `--reference` argument to the capture script accepts the local approved
HTML path and records its actual hash. Without that file the visual hash is null;
the scientific capture still works. The script never claims visual acceptance.
Regeneration replaces only this package's evidence files, including capture time
and hashes; unchanged scientific payloads remain deterministic.

`verify_package.py` validates the captured resource items against both authoritative
Pydantic models and published JSON Schemas, checks payload hashes and replay facts,
and checks storyboard timing, slide count, disclosures, JSON and local links. It
does not run the pending frontend acceptance specification.

## Verification status

Command results below were recorded during the initial submission-preparation
phase against application commit `036df20`. The full-suite counts are retained as
dated software evidence; they are not new test runs performed by the local
preservation review below. They do not certify visual fidelity or clinical validity.

| Check                                                         | Scope/status                                                                                      |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Isolated seed and stored-result comparison                    | Passed; counts and IDs above                                                                      |
| Official guide retrieval                                      | HTTP 200; 2026 guides read directly on the review date                                            |
| Official/primary-source retrieval metadata                    | [reference-checks.json](evidence/reference-checks.json); no full source articles copied           |
| Captured resource contracts and document checks               | 25 actual API items validated with Pydantic and JSON Schema; payload hashes and replay facts pass |
| Storyboard and slide structure                                | 29-second plan, 53 narration words, seven slides; actual exported media not yet produced          |
| `python -m pytest` in backend                                 | 813 passed                                                                                        |
| Backend Ruff lint/format and `scripts.export_schemas --check` | Passed; 114 Python files already formatted; schemas current                                       |
| `python -m app.scenarios replay all --validate`               | All five scenarios pass; 765 embedded contract payloads validated                                 |
| Bridge `npm run check`                                        | Contract drift, strict types and formatting passed                                                |
| Bridge `npm test`                                             | 49 passed, including an isolated real HTTP workflow                                               |
| Existing frontend `npm test`                                  | 116 passed; confirms current behavior, not Demo 6 visual acceptance                               |
| Existing frontend typecheck and Oxlint                        | Passed without editing frontend source                                                            |
| Existing frontend HTTP production build                       | Passed; build output is not evidence of Demo 6 visual fidelity                                    |
| New documentation verification script Ruff/format             | Passed                                                                                            |
| Matching Demo 6 implementation                                | Pending Silvio's final source                                                                     |
| Browser visual regression at matching viewports               | Not run; no visual pass is claimed                                                                |
| Actual video export duration / rendered slide deck            | Not produced; drafts only                                                                         |
| Local Event and administrative eligibility                    | Pending, by explicit team instruction                                                             |
| Model versions, additional tools and generated media          | Pending final team review                                                                         |
| Public links and final submission                             | Not published or submitted by this task                                                           |

## Local preservation review

Reviewed on **2026-11-15** following explicit authorization to create a local
documentation commit on `feature/frontend-bridge`. This review preserves the
drafts; it does not approve the final application or authorize publication.

- Secret-pattern scanning and manual review found no credentials, private keys,
  authentication tokens or credential-bearing URLs in the package. Evaluation IDs,
  source commits and SHA-256 digests are provenance, not access credentials.
- Quantitative scientific statements match the captured simulated evidence and
  authoritative contracts. No unsupported scientific claim was identified within
  the assessed scope. Clinical validation, diagnostic performance, treatment and
  NASA endorsement are not established or claimed.
- Demo 6 visual acceptance, actual media exports, administrative eligibility,
  public links, model versions and separate AI/data integrations remain pending.
  Future HTTP layout requirements are explicitly requirements, not completed work.
- Documentation consistency was rerun: 25 API items pass Pydantic and JSON Schema
  validation; payload hashes, replay facts, local links, disclosures, captions,
  the 29-second plan and seven-slide structure pass. The 25 frontend acceptance
  scenarios remain marked not executed.
- Dependency declarations and lockfile hashes match the recorded inventory.
  Existing evidence files are preserved byte for byte; no dataset is regenerated.
- English-language review, documentation-tool Ruff/format checks, Node syntax and
  the configured Markdown/JSON/JavaScript formatting checks pass.

The local commit is created only after the staged file list is limited to this
directory and Git's staged whitespace check passes. Its SHA and exact file list
are recorded by Git. No frontend, backend or bridge source is changed or retested
as part of this preservation review; the earlier full-suite results remain above.

## Unchanged boundaries

Only `docs/submission-2026/` is modified by this task. The frontend, FastAPI routes,
scientific algorithms, shared models/schemas, Marco's code, the separate AI
module and Exercise's NASA pipeline are unchanged. The existing test server/helper
was reused during initial capture, not edited. The initial drafting phase made no
commit. The separately authorized preservation commit contains only this directory.
No push, merge, reset, public-sharing change or NASA submission is performed.
