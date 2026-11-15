# NASA resource use, provenance and acknowledgments

Reviewed on **2026-11-15**. This ledger distinguishes external context, numerical
input data, methods and assets. It does not imply NASA affiliation or endorsement.

## Current-use statement

Every crew measurement in the assessed replay is synthetic and labelled
`source: "simulated"`. The mission seeder supplies those deterministic inputs.
The demonstrated computations do not ingest a NASA or Space Agency Partner
observational dataset. NASA resources inform the problem framing and domain choice;
they do not set the replay values or screening thresholds.

The final approved interface has not yet been shown to contain a NASA evidence
panel. This package cites NASA resources directly and prepares the narrative;
it does not claim that an integrated Research Lens or live retrieval system exists.
Exercise's separate NASA data workstream needs its own data and integration review.

## NASA resource ledger

| Resource                                                                                                                                                     | Supported use here                                                                                       | Boundary                                                                                          |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| [NASA HRP: 5 Hazards of Human Spaceflight](https://www.nasa.gov/hrp/hazards/)                                                                                | Spaceflight-context framing: radiation, isolation/confinement, distance, gravity and closed environments | Does not validate any OrbitVitals algorithm                                                       |
| [NASA HRP: Risks of Human Spaceflight](https://www.nasa.gov/hrp/risks/)                                                                                      | Context for choosing monitoring domains                                                                  | Not a patient dataset or a diagnostic rulebook                                                    |
| [NASA: Inadequate Sleep and Irregular Schedules](https://www.nasa.gov/reference/risk-from-inadequate-sleep-and-irregular-schedules/)                         | Motivation for the sleep demonstration and human review                                                  | The replay does not infer NASA's listed adverse outcomes                                          |
| [NASA: Reduced Cardiorespiratory and Musculoskeletal Fitness](https://www.nasa.gov/reference/risk-of-reduced-cardiorespiratory-and-musculoskeletal-fitness/) | Context for activity monitoring and individual variability                                               | Demo exercise targets are not NASA prescriptions                                                  |
| [NASA OCHMO-TB-031 Exercise Overview](https://www.nasa.gov/ochmo-tb-031-exercise-overview-2/)                                                                | Earlier project research supporting the principle of individual comparison                               | This package does not claim standards compliance; prior review is in the existing evidence matrix |

The four HRP pages were rechecked through their original NASA pages. The technical
brief is retained as an earlier project reference; its detailed contents were not
independently re-audited in this task. No NASA photograph, logo, mission insignia
or other agency artwork is reproduced in this package.

## Input-to-output provenance

| Stage                  | Actual source                                                 | What is preserved                                                         |
| ---------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Simulated observations | `backend/app/demo_seed/dataset.py`, reusing scenario fixtures | Canonical units, opaque IDs, aware UTC timestamps and `source: simulated` |
| Quality assessment     | `backend/app/algorithms/data_quality.py`                      | Actual status, flags, notes, completeness and algorithm identity          |
| Personal reference     | `backend/app/algorithms/personal_baseline.py`                 | Actual statistics, phase, window, sample count and establishment notes    |
| Sleep result           | `backend/app/domains/sleep/` through the existing API         | Stored evaluation ID, finding, explanation, policy summary and provenance |
| Retrieval/display      | Existing TypeScript bridge                                    | Schema checks; no replacement result, new threshold or LLM paraphrase     |
| Submission evidence    | [Captured JSON/CSV](evidence/)                                | Actual payloads plus a separate manifest; no extra API fields             |

The CSV is a presentation extract of the bridge's last Noor sleep window. Blank
values mean missing nights, not zero. It is not a NASA dataset. The JSON files
remain compatible with existing resource schemas; the manifest is explicitly
documentation metadata, not a new public API contract.

## Statistical and software references

- [NIST/SEMATECH: Detection of Outliers](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm).
  Source for the modified z-score screening documented in the baseline implementation.
- [NIST Dataplot: Theil-Sen fit](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/ts_fit.htm).
  Source for the sleep domain's descriptive slope estimator. Application-specific
  effect-size and sufficiency gates are demonstration policies, not sourced norms.
- [Python 3.11 statistics](https://docs.python.org/3.11/library/statistics.html).
  Arithmetic/statistical primitives used by the pure-Python engines.
- [FastAPI](https://fastapi.tiangolo.com/), [Pydantic](https://docs.pydantic.dev/),
  [Uvicorn](https://www.uvicorn.org/), [JSON Schema](https://json-schema.org/),
  [React](https://react.dev/), [TypeScript](https://www.typescriptlang.org/),
  [Vite](https://vite.dev/) and [Ajv](https://ajv.js.org/).
  Implementation/contract tools, not sources of medical thresholds.
- [pytest](https://docs.pytest.org/), [Ruff](https://docs.astral.sh/ruff/),
  [Vitest](https://vitest.dev/), [Testing Library](https://testing-library.com/),
  [jsdom](https://github.com/jsdom/jsdom), [Oxlint](https://oxc.rs/docs/guide/usage/linter.html)
  and [Prettier](https://prettier.io/). Verification and development tooling.

The [dependency inventory](software-inventory.json) records direct declarations,
resolved versions and license fields where the lockfiles provide them. This includes
support packages such as `pydantic-settings`, `httpx2`, Python `jsonschema` and
`ajv-formats`, as well as the tools named above. It is not a complete license audit.
The exact dependency versions are in `backend/requirements*.txt`,
`frontend/package-lock.json` and `integrations/frontend-bridge/package-lock.json`.
Keep their transitive license notices with any distributed build. The repository
declares [Apache License 2.0](../../LICENSE); that does not replace third-party
licenses or establish rights to other agents' media.

## Contributor and asset acknowledgments

Credit Andrea, Marco and Silvio using their
[confirmed roles](ai-tools-and-credits.md). Credit Silvio for the approved Demo 6
UI/UX and visual implementation. Acknowledge the maintainers of the tools and
scientific references actually used. Acknowledging NASA material does not imply
collaboration, certification or endorsement.

The supplied HTML is a compiled reference, not a complete source-attribution
inventory. Before publication, confirm the origin and licenses of its icons,
illustrations, fonts, audio, animations and any external code. System fonts being
requested by CSS are different from redistributing font files. This package has
not invented a third-party icon library or asserted that every asset was hand-drawn.

## Gate for any later NASA dataset or model claim

Before adding another contributor's pipeline to the submission, obtain the actual
source URL/accession, version or retrieval date, file/license terms, processing
steps, relevant population/mission context, units, exclusions and exact inputs used.
Reproduce the final output and identify which claims it supports. For a model,
also record the checkpoint/revision, license, inference settings, role in the
pipeline, evaluation evidence and limitations. A model's pretraining or a citation
to a paper is not proof that NASA measurements enter this project's computation.

Until those checks pass, keep external dataset integration, RAG and MedGemma out of
the demonstrated-use claims. Do not describe a planned pipeline as completed merely
because its owner is developing it concurrently.
