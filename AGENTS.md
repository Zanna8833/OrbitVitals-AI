# AGENTS.md

Shared development conventions for OrbitVitals AI. They apply to every contributor,
human or AI coding agent. `CLAUDE.md` imports this file, so the rules live here only.

## Project

OrbitVitals AI is an explainable health-monitoring prototype for long-duration space
missions, built for the NASA Space Apps Challenge 2026. It is a research prototype,
not a medical device.

| Layer | Technology | Location |
| --- | --- | --- |
| Frontend | Flutter Web (Dart) | `frontend/` |
| Backend API | Python 3.11, FastAPI | `backend/app/api/` |
| Scientific algorithms | Python 3.11 | `backend/app/algorithms/`, `backend/app/domains/` |
| RAG | Separate Python module | `rag/` |
| Shared data contracts | Pydantic models, exported as JSON Schema | `backend/app/models/`, `schemas/` |

## Ownership

Work happens in parallel, so every area has one owner. Fill in the names below.

| Area | Path | Owner |
| --- | --- | --- |
| Frontend | `frontend/` | to be assigned |
| API layer and configuration | `backend/app/api/`, `backend/app/core/` | to be assigned |
| Cross-domain algorithms | `backend/app/algorithms/` | to be assigned |
| Sleep | `backend/app/domains/sleep/` | to be assigned |
| Physical activity | `backend/app/domains/physical_activity/` | to be assigned |
| Nutrition | `backend/app/domains/nutrition/` | to be assigned |
| RAG | `rag/` | to be assigned |
| Shared contracts | `backend/app/models/`, `schemas/`, `docs/api-contracts.md` | whole team |

- Change only the areas you own. For anything else, ask the owner or open an issue.
- Shared contracts and this file change through a pull request reviewed by the owners
  it affects.
- Tests live with their area: `backend/tests/` mirrors `backend/app/`.

## Commands

Run backend commands from `backend/`, inside a Python 3.11 virtual environment.

```bash
python -m venv .venv
.venv\Scripts\activate               # Windows. On macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt

uvicorn app.main:app --reload        # API on http://localhost:8000, docs on /docs
pytest                               # run the test suite
ruff check .                         # lint
ruff format .                        # format
python -m scripts.export_schemas     # regenerate /schemas after a contract change
```

Frontend commands (`flutter analyze`, `flutter test`, `dart format .`) run from
`frontend/` once the Flutter project exists.

## Architecture rules

1. Backend dependencies point one way: `api` -> `domains` -> `algorithms` -> `models`.
   `models` imports nothing else from the app.
2. Scientific code (`algorithms`, `domains`) is pure Python. It never imports FastAPI
   or `app.api`, so it can be developed and tested without the web layer.
   `backend/tests/architecture` enforces rules 1 and 2.
3. Routes stay thin: validate the request, call domain code, return a contract model.
4. The frontend talks to the backend only over HTTP, as described in
   `docs/api-contracts.md`.
5. The RAG module is independent: it does not import backend code and the backend does
   not import its internals. Their interface is agreed with the RAG owner before either
   side depends on it.

## Data contracts

- The Pydantic models in `backend/app/models/` are the single source of truth.
- The files in `schemas/` are generated from them. Never edit them by hand.
- To change a contract:
  1. Edit the model in `backend/app/models/`.
  2. Run `python -m scripts.export_schemas` from `backend/`.
  3. Update the example in `schemas/examples/` and `docs/api-contracts.md`.
  4. Run `pytest`, and commit the model, schemas, examples and docs together.
- A contract change affects the frontend, so announce it to the team before merging.
- JSON conventions:
  - Field names and enum values are `snake_case`.
  - Timestamps are RFC 3339 strings with a time zone, in UTC (`2026-11-14T08:30:00Z`).
  - Every value of a metric uses that metric's canonical unit, listed in
    `schemas/metric_catalog.json`. Convert units where data enters the system.
  - Identifiers are opaque strings. Do not parse them.
  - Unknown fields are rejected.

## Scientific integrity

- Do not invent clinical thresholds, reference ranges or validation results.
- Every threshold, constant or formula cites its source in a comment next to the code.
  With no source, leave the logic unimplemented and say so explicitly.
- Do not describe an algorithm as validated unless there is evidence in the repository.
- Synthetic data is always labelled: measurements use `source: "simulated"`.
- Outputs support decisions made by people. Do not word them as diagnoses.

## Code conventions

- English only: source code, comments, commit messages and documentation.
- Python: version 3.11, type hints on public functions, `ruff` for linting and
  formatting, line length 100. Prefer pure functions with explicit inputs and outputs.
- Dart: `dart format` and `flutter analyze` with no warnings.
- Tests: `pytest`, deterministic, no network access. New behaviour comes with tests.
- Pin new Python dependencies to an exact version in `requirements*.txt`.

## Git workflow

- Work on short-lived branches named `<area>/<short-description>`, for example
  `sleep/duration-baseline`, and open a pull request into `main`.
- Keep pull requests small and limited to one area.
- Before pushing, `ruff check .`, `ruff format --check .` and `pytest` must pass.
- Never commit secrets, credentials or `.env` files. Document new settings in
  `backend/.env.example`.
- AI agents never commit, push or rewrite history without explicit approval from the
  person they are working with, and never modify files outside the area of the task
  without asking.
