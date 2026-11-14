# API contracts

Contract between the Flutter Web frontend and the FastAPI backend.

**Status: proposal, version 0.1.** Only the health check is implemented. Every other
endpoint describes the intended contract, so that the frontend can be built before the
backend exists. Each endpoint below is marked *Implemented* or *Proposed*. Proposed
endpoints may change after team review; see [Open points](#open-points).

OrbitVitals AI is a research prototype, not a medical device. Statuses returned by the
API are labels produced by algorithms that are not implemented yet, and no clinical
threshold is part of this contract.

## General conventions

| Topic | Rule |
| --- | --- |
| Base URL | `http://localhost:8000/api/v1` in development. Keep it configurable in the client |
| Format | JSON, UTF-8, in requests and responses |
| Naming | Field names and enum values are `snake_case` |
| Timestamps | RFC 3339 strings with a time zone, in UTC, e.g. `2026-11-14T08:30:00Z` |
| Identifiers | Opaque strings of 1 to 128 characters. Do not parse them |
| Units | Every value uses the canonical unit of its metric, listed in [metric_catalog.json](../schemas/metric_catalog.json) |
| Optional fields | Responses always include every field; an absent value is `null` |
| Unknown fields | Rejected in requests with status `422` |
| Lists | Returned as `{"items": [...]}` |
| CORS | Requests from any `localhost` or `127.0.0.1` port are allowed by default |
| Authentication | None yet |

The backend also serves interactive documentation at `http://localhost:8000/docs` and
an OpenAPI document at `/openapi.json`. Both cover implemented endpoints only.

In Dart, map `snake_case` keys to `lowerCamelCase` fields, for example with
`@JsonSerializable(fieldRename: FieldRename.snake)` from `json_serializable`.

## Data models

The models are defined once and shared by every endpoint. The schema files are the
reference for field names, types and descriptions.

| Model | Purpose | Schema | Example |
| --- | --- | --- | --- |
| `PhysiologicalMeasurement` | One value of one metric for one crew member | [schema](../schemas/physiological_measurement.schema.json) | [example](../schemas/examples/physiological_measurement.example.json) |
| `DataQuality` | Quality assessment of a measurement or of a window of measurements | [schema](../schemas/data_quality.schema.json) | [example](../schemas/examples/data_quality.example.json) |
| `PersonalBaseline` | Reference statistics of one metric for one crew member | [schema](../schemas/personal_baseline.schema.json) | [example](../schemas/examples/personal_baseline.example.json) |
| `MissionPhase` | One entry of a mission timeline | [schema](../schemas/mission_phase.schema.json) | [example](../schemas/examples/mission_phase.example.json) |
| `EvaluationResult` | Evaluation of one health domain over a time window, with per-metric findings | [schema](../schemas/evaluation_result.schema.json) | [example](../schemas/examples/evaluation_result.example.json) |

Enumerations:

| Enumeration | Values |
| --- | --- |
| `HealthDomain` | `vital_signs`, `sleep`, `physical_activity`, `nutrition` |
| `MetricType` | See [metric_catalog.json](../schemas/metric_catalog.json) |
| `MeasurementSource` | `wearable`, `medical_device`, `manual_entry`, `simulated` |
| `QualityStatus` | `not_assessed`, `acceptable`, `degraded`, `unusable` |
| `QualityFlag` | `missing_data`, `out_of_sensor_range`, `signal_artifact`, `duplicate`, `insufficient_samples` |
| `BaselineStatus` | `insufficient_data`, `provisional`, `established` |
| `MissionPhaseType` | `pre_flight`, `launch`, `in_flight`, `return_to_earth`, `post_flight` |
| `EvaluationStatus` | `nominal`, `attention`, `alert`, `insufficient_data` |

The client should tolerate enum values it does not know, because the lists may grow.

### Data quality and physiological status

The contract answers two separate questions with two separate types. Present them
separately in the interface.

| Question | Type | Where it appears |
| --- | --- | --- |
| How far can the data be trusted? | `DataQuality`, with `QualityStatus` and `QualityFlag` | `data_quality` on measurements, baselines, findings and evaluations |
| What is the physiological status of the crew member? | `EvaluationStatus` | `status` on `EvaluationResult` and on each entry of `findings` |

The two types share no values. `DataQuality` describes the data and never the crew
member. `EvaluationStatus` describes the crew member relative to the personal baseline;
its value `insufficient_data` means that no physiological status could be determined.

`BaselineStatus` is a third notion: how far a personal baseline can be relied upon.

## Endpoints

| Method | Path | Purpose | Status |
| --- | --- | --- | --- |
| `GET` | `/health` | Check that the API is up | Implemented |
| `GET` | `/metrics` | List the supported metrics | Proposed |
| `GET` | `/missions/{mission_id}/phases` | Get the timeline of a mission | Proposed |
| `POST` | `/measurements` | Send a batch of measurements | Proposed |
| `GET` | `/crew-members/{crew_member_id}/measurements` | Read measurements of a crew member | Proposed |
| `GET` | `/crew-members/{crew_member_id}/baselines` | Read personal baselines of a crew member | Proposed |
| `GET` | `/crew-members/{crew_member_id}/evaluations` | Read evaluation results of a crew member | Proposed |

Paths are relative to the base URL.

### GET /health

*Implemented.* Reports that the API process is running.

Response `200`:

```json
{
  "status": "ok",
  "service": "orbitvitals-api",
  "version": "0.1.0",
  "timestamp": "2026-11-14T10:36:29.749986Z"
}
```

### GET /metrics

*Proposed.* Returns the metric catalog, with the same entries as
[metric_catalog.json](../schemas/metric_catalog.json). Until the endpoint exists, the
client can bundle that file.

Response `200`:

```json
{
  "items": [
    {
      "metric": "heart_rate",
      "domain": "vital_signs",
      "unit": "bpm",
      "description": "Heart rate."
    }
  ]
}
```

### GET /missions/{mission_id}/phases

*Proposed.* Returns the phases of a mission, ordered by `start_time`. The current phase
is the one whose `end_time` is `null` or in the future.

Response `200`: `{"items": [MissionPhase, ...]}`

### POST /measurements

*Proposed.* Stores a batch of measurements. The client generates `measurement_id` and
leaves `data_quality` out; the backend returns the stored measurements with
`data_quality` filled in.

Request:

```json
{
  "measurements": [
    {
      "measurement_id": "meas-0001",
      "crew_member_id": "crew-001",
      "metric": "heart_rate",
      "unit": "bpm",
      "value": 58.0,
      "measured_at": "2026-11-14T08:30:00Z",
      "source": "simulated",
      "device_id": "sim-wearable-01"
    }
  ]
}
```

Response `201`: `{"items": [PhysiologicalMeasurement, ...]}`

A measurement whose `unit` is not the canonical unit of its `metric` is rejected with
status `422`.

### GET /crew-members/{crew_member_id}/measurements

*Proposed.* Returns measurements ordered by `measured_at`, oldest first.

| Query parameter | Type | Meaning |
| --- | --- | --- |
| `metric` | `MetricType`, optional | Return only this metric |
| `start` | timestamp, optional | Return measurements taken at or after this instant |
| `end` | timestamp, optional | Return measurements taken before this instant |
| `limit` | integer, optional | Maximum number of items |

Response `200`: `{"items": [PhysiologicalMeasurement, ...]}`

### GET /crew-members/{crew_member_id}/baselines

*Proposed.* Returns the personal baselines of a crew member.

| Query parameter | Type | Meaning |
| --- | --- | --- |
| `metric` | `MetricType`, optional | Return only this metric |
| `mission_phase` | `MissionPhaseType`, optional | Return only baselines built from this phase |

Response `200`: `{"items": [PersonalBaseline, ...]}`

### GET /crew-members/{crew_member_id}/evaluations

*Proposed.* Returns evaluation results ordered by `window_end`, most recent first.

| Query parameter | Type | Meaning |
| --- | --- | --- |
| `domain` | `HealthDomain`, optional | Return only this domain |
| `start` | timestamp, optional | Return evaluations whose window ends at or after this instant |
| `end` | timestamp, optional | Return evaluations whose window ends before this instant |

Response `200`: `{"items": [EvaluationResult, ...]}`

Each `EvaluationResult` carries an overall `status` and `summary` for the domain, plus
one entry in `findings` per metric with the observed value, the baseline it was
compared with, the deviation and a plain-language `explanation`.

## Errors

Errors use the standard FastAPI format.

| Status | Meaning | Body |
| --- | --- | --- |
| `404` | The resource does not exist | `{"detail": "..."}` |
| `422` | The request is not valid | `{"detail": [{"type": "...", "loc": ["body", "..."], "msg": "...", "input": ...}]}` |

In a `422` response, `loc` is the path of the invalid field and `msg` describes the
problem.

## Developing the frontend before the backend

- Use the files in [schemas/examples/](../schemas/examples/) as fixtures for proposed
  endpoints. They are validated against the contracts by the backend test suite.
- Build the Dart model classes from the schema files.
- Read units and domains from [metric_catalog.json](../schemas/metric_catalog.json)
  instead of hard-coding them.
- Every value in the examples is synthetic. Statuses in the examples were assigned by
  hand and do not reflect any real classification rule.

## Open points

These decisions are still to be made by the team. The contract will be updated as they
are settled.

1. The list of metrics and their canonical units.
2. The list of mission phases, for example whether `in_flight` should be split.
3. The evaluation status labels. The rules behind them belong to the scientific
   algorithms and are not defined yet.
4. Resources to list missions and crew members, which the frontend needs for selection.
5. How evaluations are triggered: on ingestion, on a schedule or on request.
6. What happens when a `measurement_id` is sent twice.
7. Pagination of list endpoints.
8. Authentication.
9. Explanations backed by the RAG module. That contract is defined together with the
   RAG owner and is not covered by this version.

## Changing this contract

Follow the steps in "Data contracts" in [AGENTS.md](../AGENTS.md): change the model,
regenerate the schemas, update the example and this document, and announce the change
to the team before merging.
