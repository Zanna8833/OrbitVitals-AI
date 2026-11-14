# Shared data contracts

Language-neutral description of the data exchanged between the frontend, the backend
and the RAG module.

| Contract | Schema | Example |
| --- | --- | --- |
| Physiological measurement | [physiological_measurement.schema.json](physiological_measurement.schema.json) | [example](examples/physiological_measurement.example.json) |
| Data quality | [data_quality.schema.json](data_quality.schema.json) | [example](examples/data_quality.example.json) |
| Personal baseline | [personal_baseline.schema.json](personal_baseline.schema.json) | [example](examples/personal_baseline.example.json) |
| Mission phase | [mission_phase.schema.json](mission_phase.schema.json) | [example](examples/mission_phase.example.json) |
| Evaluation result | [evaluation_result.schema.json](evaluation_result.schema.json) | [example](examples/evaluation_result.example.json) |

[metric_catalog.json](metric_catalog.json) lists every metric with its domain and its
canonical unit.

## These files are generated

The `*.schema.json` files and `metric_catalog.json` are generated from the Pydantic
models in `backend/app/models/`. Do not edit them by hand: the test suite fails when
they differ from the models.

To change a contract, edit the model and regenerate:

```bash
cd backend
python -m scripts.export_schemas
pytest
```

The example files in `examples/` are written by hand. The test suite validates each of
them against both the schema file and the model, so keep them up to date.

## Conventions

- JSON Schema draft 2020-12. Each file is self-contained: nested types are in `$defs`.
- Field names and enum values are `snake_case`.
- Timestamps are RFC 3339 strings with a time zone, in UTC.
- Unknown fields are rejected (`additionalProperties: false`).
- Data quality and physiological status are separate. `DataQuality` describes how far
  the data can be trusted; `EvaluationStatus` describes the crew member. The two share
  no values.
- Rules that JSON Schema cannot express are enforced by the backend:
  - `unit` must be the canonical unit of `metric`, as listed in `metric_catalog.json`;
  - the end of an interval or window is never earlier than its start.

## Status of the content

- The metric list, the mission phases and the status labels are an initial proposal,
  open to review by the team.
- Status values such as `nominal` or `degraded` are labels. The rules that assign them
  belong to the scientific algorithms, which are not implemented yet. No clinical
  threshold is defined anywhere in these contracts.
- Every value in `examples/` is synthetic and illustrative. Statuses in the examples
  were assigned by hand, not computed.
