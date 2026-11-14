# OrbitVitals-AI

Explainable health monitoring for long-duration space missions — NASA Space Apps Challenge 2026

OrbitVitals AI is a research prototype. It is not a medical device and its outputs are
not diagnoses.

## Stack

- Frontend: Flutter Web (Dart)
- Backend: Python 3.11 + FastAPI
- Scientific algorithms: Python
- RAG: separate Python module

## Repository layout

```
OrbitVitals-AI/
├── backend/                 Python backend
│   ├── app/
│   │   ├── main.py          FastAPI application factory
│   │   ├── core/            Configuration
│   │   ├── api/             HTTP layer
│   │   ├── models/          Shared data contracts (source of truth)
│   │   ├── algorithms/      Cross-domain scientific algorithms (not implemented yet)
│   │   └── domains/         sleep/, physical_activity/, nutrition/ (not implemented yet)
│   ├── scripts/             Developer scripts (schema export)
│   └── tests/               Automated tests, mirroring app/
├── frontend/                Flutter Web client (to be scaffolded by its owner)
├── rag/                     RAG module (owned by its developer)
├── schemas/                 Generated JSON Schemas, metric catalog and example payloads
├── docs/
│   └── api-contracts.md     API contract between frontend and backend
├── AGENTS.md                Shared development conventions
└── CLAUDE.md                Claude Code entry point, imports AGENTS.md
```

## Quick start (backend)

Requires Python 3.11.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate               # Windows. On macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt

uvicorn app.main:app --reload        # http://localhost:8000/api/v1/health
pytest
```

Interactive API documentation is served at `http://localhost:8000/docs`.

## Documentation

- [docs/api-contracts.md](docs/api-contracts.md): API contract for frontend development.
- [schemas/README.md](schemas/README.md): shared data contracts and how to change them.
- [backend/README.md](backend/README.md): backend setup and commands.

## License

Apache License 2.0. See [LICENSE](LICENSE).
