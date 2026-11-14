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
| `app/algorithms/` | Cross-domain scientific algorithms. Not implemented yet |
| `app/domains/` | `sleep/`, `physical_activity/`, `nutrition/`. Not implemented yet |
| `scripts/` | Developer scripts |
| `tests/` | Test suite, mirroring `app/` |

Scientific code must not import FastAPI or `app.api`. See "Architecture rules" in
[AGENTS.md](../AGENTS.md); `tests/architecture` enforces them.

## Adding an endpoint

1. Create a module in `app/api/routes/` with an `APIRouter`.
2. Include it in `app/api/router.py`.
3. Use the models from `app/models/` as request and response types.
4. Add tests in `tests/api/` and update `docs/api-contracts.md`.
