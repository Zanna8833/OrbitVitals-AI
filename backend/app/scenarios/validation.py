"""Offline validation of replay payloads against the repository's existing schemas."""

import json
from collections.abc import Iterator
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.models import CONTRACT_MODELS, MetricFinding
from app.scenarios.codec import canonical_json
from app.scenarios.models import ReplayResult

# Resolve from this module, never the process working directory or an HTTP URL.
SCHEMA_DIRECTORY = Path(__file__).resolve().parents[3] / "schemas"


def _contract_objects(value: Any, path: str = "replay") -> Iterator[tuple[str, str, BaseModel]]:
    names = {model: name for name, model in CONTRACT_MODELS.items()}
    if isinstance(value, BaseModel):
        name = names.get(type(value))
        if name is not None:
            yield path, name, value
        elif isinstance(value, MetricFinding):
            yield path, "metric_finding", value
        for field_name in type(value).model_fields:
            yield from _contract_objects(getattr(value, field_name), f"{path}.{field_name}")
    elif is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            yield from _contract_objects(getattr(value, field.name), f"{path}.{field.name}")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _contract_objects(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _contract_objects(item, f"{path}[{index}]")


def validate_contracts(result: ReplayResult, *, schema_directory: Path | None = None) -> int:
    """Validate the local envelope and every embedded shared contract, without network I/O.

    Return the number of validated shared payloads, including nested occurrences.
    Rejected raw candidates are metadata, not PhysiologicalMeasurement payloads.
    jsonschema is an existing pinned development dependency and is needed only for
    explicit validation, not for replay execution or human/JSON serialization.
    """
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError

    payload = json.loads(canonical_json(result))
    # Revalidate serialized values too: Pydantic models can be mutated after creation.
    restored = ReplayResult.model_validate(payload)
    local_schema = ReplayResult.model_json_schema()
    Draft202012Validator.check_schema(local_schema)
    Draft202012Validator(local_schema).validate(payload)

    directory = schema_directory if schema_directory is not None else SCHEMA_DIRECTORY
    schemas = {
        name: json.loads((directory / f"{name}.schema.json").read_text(encoding="utf-8"))
        for name in CONTRACT_MODELS
    }
    # MetricFinding is already defined inside EvaluationResult's committed schema;
    # use that definition for standalone observation findings without a new schema.
    schemas["metric_finding"] = {
        "$schema": schemas["evaluation_result"]["$schema"],
        "$ref": "#/$defs/MetricFinding",
        "$defs": schemas["evaluation_result"]["$defs"],
    }
    validators = {}
    for name, schema in schemas.items():
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            raise ValueError(f"Invalid committed schema {name}: {error.message}") from error
        validators[name] = Draft202012Validator(schema)

    count = 0
    for path, name, contract in _contract_objects(restored):
        errors = list(validators[name].iter_errors(contract.model_dump(mode="json")))
        if errors:
            raise ValueError(f"Existing schema validation failed at {path}: {errors[0].message}")
        count += 1
    return count
