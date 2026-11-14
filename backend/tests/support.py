"""Helpers to load the shared schema and example files from /schemas."""

import json
from typing import Any

from scripts.export_schemas import EXAMPLES_DIR, SCHEMAS_DIR


def load_schema(name: str) -> dict[str, Any]:
    """Load the generated JSON Schema of the contract called `name`."""
    return json.loads((SCHEMAS_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def load_example(name: str) -> dict[str, Any]:
    """Load the example payload of the contract called `name`."""
    return json.loads((EXAMPLES_DIR / f"{name}.example.json").read_text(encoding="utf-8"))
