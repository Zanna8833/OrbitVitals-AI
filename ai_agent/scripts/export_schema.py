"""Write the JSON Schema of the agent response for frontend developers.

Usage, from `ai_agent/`:

    python -m scripts.export_schema            # regenerate schemas/agent_response.schema.json
    python -m scripts.export_schema --check    # fail if the file is out of date

The schema belongs to this proof of concept. It is not one of the shared contracts in
the repository-level `schemas/` directory.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from orbit_agent.models import AgentResponse, ExplanationRequest

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
MODELS = {
    "agent_response.schema.json": AgentResponse,
    "explanation_request.schema.json": ExplanationRequest,
}


def _render(model: type) -> str:
    return json.dumps(model.model_json_schema(), indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only compare, do not write")
    arguments = parser.parse_args()
    stale = []
    for name, model in MODELS.items():
        path = SCHEMA_DIR / name
        rendered = _render(model)
        if arguments.check:
            if not path.exists() or path.read_text(encoding="utf-8") != rendered:
                stale.append(name)
        else:
            SCHEMA_DIR.mkdir(exist_ok=True)
            path.write_text(rendered, encoding="utf-8")
            print(f"Wrote {path}")
    if stale:
        print(f"Out of date: {', '.join(stale)}. Run python -m scripts.export_schema")
        return 1
    if arguments.check:
        print("Schemas are up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
