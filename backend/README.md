# Backend

Python 3.11 + FastAPI. Hosts the HTTP API, the shared data contracts and the scientific
code.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate               # Windows. On macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
```

Configuration is optional. To override the defaults, copy `.env.example` to `.env`.

## Commands

Run from this directory.

| Task | Command |
| --- | --- |
| Start the API with auto-reload | `uvicorn app.main:app --reload` |
| Run the tests | `pytest` |
| Lint | `ruff check .` |
| Format | `ruff format .` |
| Regenerate `/schemas` | `python -m scripts.export_schemas` |
| Check that `/schemas` is up to date | `python -m scripts.export_schemas --check` |

The API listens on `http://localhost:8000`. Interactive documentation is at `/docs`
and the OpenAPI document at `/openapi.json`.

## Layout

| Path | Content |
| --- | --- |
| `app/main.py` | Application factory and CORS setup |
| `app/core/` | Configuration |
| `app/api/` | HTTP routes. Register new route modules in `app/api/router.py` |
| `app/models/` | Shared data contracts, the source of truth for `/schemas` |
| `app/algorithms/` | Data Quality and Personal Baseline engines |
| `app/domains/` | Sleep and physical-activity monitoring; other domain owners' modules |
| `app/services/` | Application commands and scientific orchestration |
| `app/repositories/` | Isolated in-memory MVP repository |
| `scripts/` | Developer scripts |
| `tests/` | Test suite, mirroring `app/` |

Scientific code must not import FastAPI or `app.api`. See "Architecture rules" in
[AGENTS.md](../AGENTS.md); `tests/architecture` enforces them.

## Integrated API MVP

The API implements metric discovery, atomic measurement ingestion, filtered retrieval,
baseline generation/retrieval and sleep/activity evaluation generation/retrieval.
See [API contracts](../docs/api-contracts.md) and the
[frontend integration guide](../docs/frontend-integration.md) for complete JSON
commands, a runnable simulated workflow, scientific policy requirements and CORS setup.

Run `uvicorn app.main:app --host 127.0.0.1 --port 8000` from this directory. Keep a single
worker: records live only in this app process and disappear on restart or reload.
Sleep has no default screening policy, baselines have no default establishment
criteria, and activity completeness must be explicitly confirmed. Missing prerequisites
produce explained insufficient/provisional outputs rather than assumed results.

## Physical activity

`app.domains.physical_activity.monitor_activity` evaluates canonical exercise-duration
and active-energy measurements, explicit recording coverage, personal targets and
compatible established daily baselines. It returns the existing `EvaluationResult`
inside a domain-local report with session, daily and weekly detail. No HTTP endpoint
or unfinished quality/baseline engine is required.

See [physical activity monitoring](../docs/physical-activity-monitoring.md) for the
algorithms, assumptions, integration responsibilities and limitations. Run the clearly
labeled synthetic examples with `python -m app.domains.physical_activity.demo`;
add `--full` to include complete simulated inputs and reports.

## Synthetic presentation data

With the API running, use `python -m app.demo_seed seed --report mission-demo-report.json`
to load three synthetic crew histories and compute real baseline/sleep/activity results
through the existing HTTP endpoints. Repeat runs are idempotent for the same inputs
and backend configuration. `python -m app.demo_seed manifest` prints the offline crew,
scenario and endpoint mapping. See the [mission demo seeder guide](../docs/mission-demo-seed.md)
for exact Windows PowerShell commands, demo assumptions, reset behavior and tests.

## Adding an endpoint

1. Create a module in `app/api/routes/` with an `APIRouter`.
2. Include it in `app/api/router.py`.
3. Use the models from `app/models/` as request and response types.
4. Add tests in `tests/api/` and update `docs/api-contracts.md`.
