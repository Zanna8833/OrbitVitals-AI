# API contracts

Framework-independent JSON contract between the frontend and the FastAPI backend.

**Status: implemented MVP, version 0.1.** Health, metrics, measurement ingestion and
retrieval, baseline generation/retrieval, and sleep/activity evaluation generation/retrieval
are implemented. The mission timeline endpoint remains proposed. The shared resource
models, field names, metric identifiers and status values are unchanged. Explicit
computation commands are additive endpoints described below.

OrbitVitals AI is a research prototype, not a medical device. Statuses returned by the
API are explainable outputs of the identified algorithms, and no clinical threshold
is part of this contract. See the [frontend integration guide](frontend-integration.md)
for a runnable simulated workflow, configuration, assumptions and limitations.

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
| `GET` | `/metrics` | List the supported metrics | Implemented |
| `GET` | `/missions/{mission_id}/phases` | Get the timeline of a mission | Proposed |
| `POST` | `/measurements` | Send a batch of measurements | Implemented |
| `GET` | `/crew-members/{crew_member_id}/measurements` | Read measurements of a crew member | Implemented |
| `GET` | `/crew-members/{crew_member_id}/baselines` | Read personal baselines of a crew member | Implemented |
| `POST` | `/crew-members/{crew_member_id}/baselines` | Build a baseline from stored history and a supplied mission timeline | Implemented, additive command |
| `GET` | `/crew-members/{crew_member_id}/evaluations` | Read evaluation results of a crew member | Implemented |
| `POST` | `/crew-members/{crew_member_id}/evaluations` | Run configured sleep or activity monitoring on stored history | Implemented, additive command |

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

*Implemented.* Returns the complete canonical metric catalog, with the same entries as
[metric_catalog.json](../schemas/metric_catalog.json).

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

*Implemented.* Atomically stores 1 through 1000 measurements. The client generates
`measurement_id` and leaves `data_quality` out; the backend returns measurements with
real Data Quality Engine output. Supplied quality is replaced, never trusted as the
server assessment. UTC normalization preserves timestamp instants and metric values.

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

Identical measurement IDs/content are idempotent, including repeats within one batch.
The response contains one item per distinct submitted ID, in first-occurrence order,
and uses `201` for retries as well as new records. Content equality excludes
`data_quality`. IDs are globally unique: conflicting content or reassignment to another
crew member returns `409` and rejects the entire batch. Distinct IDs representing the
same observation are retained and assessed by the quality engine.

The engine reassesses affected crew history, including paired readings and duplicate
observations received in earlier requests. Impossible values can be stored with
`unusable` quality; ingestion does not turn a quality failure into a physiological
alert. Records outside configured device ranges have the engine's documented quality
status. No device range is assumed by default.

### GET /crew-members/{crew_member_id}/measurements

*Implemented.* Returns measurements ordered by `measured_at`, oldest first, then by ID.

| Query parameter | Type | Meaning |
| --- | --- | --- |
| `metric` | `MetricType`, optional | Return only this metric |
| `start` | timestamp, optional | Return measurements taken at or after this instant |
| `end` | timestamp, optional | Return measurements taken before this instant |
| `limit` | integer, optional | Maximum number of items, from 1 through 1000 |

Response `200`: `{"items": [PhysiologicalMeasurement, ...]}`

### GET /crew-members/{crew_member_id}/baselines

*Implemented.* Returns stored personal baselines of a crew member, newest reference
window first. GET performs no implicit generation. No stored results returns `{"items": []}`.

| Query parameter | Type | Meaning |
| --- | --- | --- |
| `metric` | `MetricType`, optional | Return only this metric |
| `mission_phase` | `MissionPhaseType`, optional | Return only baselines built from this phase |

Response `200`: `{"items": [PersonalBaseline, ...]}`

### GET /crew-members/{crew_member_id}/evaluations

*Implemented.* Returns stored evaluation results ordered by `window_end`, most recent
first, then by evaluation time and ID. GET performs no implicit evaluation.

| Query parameter | Type | Meaning |
| --- | --- | --- |
| `domain` | `HealthDomain`, optional | Return only this domain |
| `start` | timestamp, optional | Return evaluations whose window ends at or after this instant |
| `end` | timestamp, optional | Return evaluations whose window ends before this instant |
| `limit` | integer, optional | Maximum number of items, from 1 through 1000 |

Response `200`: `{"items": [EvaluationResult, ...]}`

Each `EvaluationResult` carries an overall `status` and `summary` for the domain, plus
one entry in `findings` per metric with the observed value, the baseline it was
compared with, the deviation and a plain-language `explanation`.

### Explicit computation commands

`POST /crew-members/{crew_member_id}/baselines` returns one existing `PersonalBaseline`
with status `201`. Its body is a `BaselineCommand`: `metric`, `mission_phase`, a
nonempty `mission_phases` list of existing `MissionPhase` objects, `reference_start`,
`reference_end`, and optional `computed_at`, `config`, `aggregation`, and `activity`.
The supplied timeline must describe one mission without overlapping phases. It is
used for this computation and is not a mission-directory write.

`aggregation` defaults to `measurement`. For activity comparisons use
`complete_active_day_total`, with explicit per-metric recording `coverage` and mission
day plans in `activity`. The adapter sums complete usable active-day contributions
before calling the real baseline engine. Raw session means cannot be selected as daily
activity references. No derived aggregate is inserted into raw measurement history.

With no establishment criteria, the engine returns provisional or insufficient
baselines. Optional `config.established_min_samples` and/or `established_min_span`
require a nonempty `policy_source`; this records the caller's policy, not clinical
validation. `minimum_samples`, `outlier_cutoff`, and `outlier_handling` use the engine's
documented meanings. See OpenAPI for exact types and defaults.

`POST /crew-members/{crew_member_id}/evaluations` returns one existing
`EvaluationResult` with status `201`. Its `EvaluationCommand` body contains `domain`
(`sleep` or `physical_activity`), `window_start`, `window_end`, optional `evaluated_at`,
`mission_phase`, `baseline_ids`, `sleep_config`, and `activity`. All measurements come
from the isolated crew repository; clients cannot inject evaluated values or results.

Sleep uses an explicit request `sleep_config` or configured server policy. Without
one, it returns an explained `insufficient_data` result and does not run a fictional
default screen. Activity uses explicit coverage, sessions, plans and policies; no
coverage is inferred from the number of received records. Baselines are selected
explicitly by ID, with matching crew, metric/domain, mission phase and aggregation.
Activity selection also requires `activity.baselines_comparable=true`. Reference
eligibility and historical cutoff checks remain enforced by the existing modules.

Optional computation times default to UTC server time, must not lie in the future,
and must follow the requested window end. Fixed inputs, policy, history and explicit
computation time produce deterministic IDs. Omitted times create current snapshots.
Neither command automatically runs after ingestion; the frontend controls when its
required recording and mission context is ready.

### Storage and empty results

Storage is in memory, isolated per app instance and protected for concurrent requests.
Run one worker. Restarts and development reloads erase all records. This is an MVP
repository, not a database. Unknown crew collections return `200` with `{"items": []}`.
Missing or foreign explicitly selected baseline IDs return `404`.

Backfill or changed measurement quality invalidates saved baselines/evaluations whose
crew/time windows intersect the changes, and evaluations referencing invalidated
baselines. Invalidation is conservative across metrics. Later data outside a prior
reference window preserves that baseline. Regenerate affected results explicitly.
An identical ingestion retry does not invalidate results.

## Errors

Errors use the standard FastAPI format.

| Status | Meaning | Body |
| --- | --- | --- |
| `404` | The resource does not exist | `{"detail": "..."}` |
| `409` | A measurement ID has conflicting content | `{"detail": "..."}` |
| `422` | The request is not valid | `{"detail": [{"type": "...", "loc": ["body", "..."], "msg": "...", "input": ...}]}` |

In a `422` response, `loc` is the path of the invalid field and `msg` describes the
problem.

Computation/context errors use the same `detail` array shape, with `loc` identifying
the body or query. Invalid non-finite inputs are represented safely in error JSON.
Timestamp filters require timezone information and `end > start` when both are set.

## Developing the frontend

- Use the files in [schemas/examples/](../schemas/examples/) as fixtures for proposed
  endpoints. They are validated against the contracts by the backend test suite.
- Build the Dart model classes from the schema files.
- Read units and domains from [metric_catalog.json](../schemas/metric_catalog.json)
  instead of hard-coding them.
- Every value in the examples is synthetic. Statuses in the examples were assigned by
  hand and do not reflect any real classification rule.
- Use the running API and [frontend integration guide](frontend-integration.md) for
  computed results. Shared `/schemas/examples` remain contract fixtures, not engine outputs.

## Open points

These decisions are still to be made by the team. The contract will be updated as they
are settled.

1. The list of metrics and their canonical units.
2. The list of mission phases, for example whether `in_flight` should be split.
3. Clinical/flight validation of scientific policies. The implemented module rules
   and parameter meanings are documented, but are not validated medical thresholds.
4. Resources to list missions and crew members, which the frontend needs for selection.
5. Durable storage and pagination beyond the implemented optional limits.
6. Authentication.
7. Explanations backed by the RAG module. That contract is defined together with the
   RAG owner and is not covered by this version.

## Changing this contract

Follow the steps in "Data contracts" in [AGENTS.md](../AGENTS.md): change the model,
regenerate the schemas, update the example and this document, and announce the change
to the team before merging.
