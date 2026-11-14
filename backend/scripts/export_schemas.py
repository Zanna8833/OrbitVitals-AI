"""Generate the shared files in /schemas from the Pydantic contract models.

Run from the `backend/` directory:

    python -m scripts.export_schemas          # rewrite the files
    python -m scripts.export_schemas --check  # exit with status 1 if they are stale
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.models import CONTRACT_MODELS, METRIC_CATALOG

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPO_ROOT / "schemas"
EXAMPLES_DIR = SCHEMAS_DIR / "examples"

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
GENERATED_NOTICE = (
    "Generated from backend/app/models by backend/scripts/export_schemas.py. Do not edit by hand."
)


def build_documents() -> dict[str, dict[str, Any]]:
    """Return every generated document, keyed by its file name inside /schemas."""
    documents: dict[str, dict[str, Any]] = {}
    for name, model in CONTRACT_MODELS.items():
        documents[f"{name}.schema.json"] = {
            "$schema": JSON_SCHEMA_DIALECT,
            "$comment": GENERATED_NOTICE,
            **model.model_json_schema(),
        }
    documents["metric_catalog.json"] = {
        "$comment": GENERATED_NOTICE,
        "metrics": [definition.model_dump(mode="json") for definition in METRIC_CATALOG.values()],
    }
    return documents


def stale_files() -> list[str]:
    """Return the names of the files in /schemas that are missing or out of date."""
    stale = []
    for file_name, document in build_documents().items():
        path = SCHEMAS_DIR / file_name
        if not path.exists() or json.loads(path.read_text(encoding="utf-8")) != document:
            stale.append(file_name)
    return stale


def write_documents() -> None:
    """Write every generated document to /schemas."""
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    for file_name, document in build_documents().items():
        text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
        (SCHEMAS_DIR / file_name).write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote schemas/{file_name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the shared data contracts to /schemas.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write anything; fail if the committed files are stale",
    )
    args = parser.parse_args(argv)

    if not args.check:
        write_documents()
        return 0

    stale = stale_files()
    if stale:
        print("Stale files in /schemas: " + ", ".join(stale))
        print("Run `python -m scripts.export_schemas` from backend/ and commit the result.")
        return 1
    print("Schemas are up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
