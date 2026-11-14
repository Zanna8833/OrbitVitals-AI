"""Canonical, finite JSON serialization for reproducible replay artifacts."""

import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, JsonValue


def _encode(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Replay timestamps must carry a time zone")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, timedelta):
        # Exact configuration metadata in seconds, not a physiological calculation.
        return {"seconds": value.total_seconds()}
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(f"Unsupported replay JSON value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Serialize with stable ordering, explicit Unicode, and no NaN or Infinity."""
    return (
        json.dumps(
            value, default=_encode, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )


def json_value(value: Any) -> JsonValue:
    """Convert configuration or an actual engine value into JSON-native metadata."""
    return json.loads(canonical_json(value))
