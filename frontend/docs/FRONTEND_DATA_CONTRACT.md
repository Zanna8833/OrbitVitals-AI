# OrbitVitals AI — API contract (PROPOSAL v0.2)

> **Status: frontend proposal to discuss with the backend and database colleagues. Not a final decision.**
> The matching TypeScript types are in `frontend/src/domain/types.ts`. The adapter that consumes these APIs is `frontend/src/data/http/HttpDataSource.ts`. It is covered by contract tests with a fake `fetch` (`HttpDataSource.test.ts`) that pin down the requests it sends and how it reads responses and errors, but it has **not yet been run against a real server**.
>
> Changes since v0.1: document translated into English; user-facing `message` texts are now expected in English; auto-refresh by polling implemented on the frontend (open question 5 updated).

## Conventions

| Topic | Proposal |
|---|---|
| Base URL | `/api/v1` (configurable with `VITE_API_BASE_URL`) |
| Format | JSON UTF-8, field names in `camelCase` |
| Timestamps | ISO 8601 **in UTC with the `Z` suffix** (`2026-11-14T10:15:20Z`). No local times. The frontend always displays “UTC”. |
| Two distinct times | `t` = **acquisition** time (device clock). `receivedAt` = **reception on the ground** time. They must not be confused. |
| “Now” | `GET /mission/status` returns `now`, the reference used to compute data age. In the demo it is a simulated clock. In production it is the server time. The frontend does not use the browser clock to assess freshness. |
| Units | Fixed per parameter (table below) and repeated in every series (`unit`) |
| Missing values | `value: null` + `quality: "missing"`. **Never** `0`, `-1` or interpolated values. |
| Lists | `{ "items": [...] }`. An empty list is `{"items": []}` with `200`, not `404`. |
| Simulation | Every resource containing generated data must say so (`simulated: true`) |
| Identity | No real personal data: `displayName` is a pseudonym (“Crew A”) |
| Refresh | The frontend polls every 10 s (configurable); reads must be cheap and idempotent. |

### Parameters

| `parameter` | Label | Unit | Decimals | Role |
|---|---|---|---|---|
| `heart_rate` | Heart rate | `bpm` | 0 | vital |
| `spo2` | O₂ saturation | `%` | 0 | vital |
| `resp_rate` | Respiratory rate | `breaths/min` | 0 | vital |
| `motion` | Motion (accelerometer RMS) | `g` | 2 | context (helps recognise artifacts) |

New parameters are added to the enum in agreement with the frontend.

### Measurement quality

| `quality` | Meaning |
|---|---|
| `good` | No issue reported by the acquisition chain |
| `uncertain` | Possible disturbance: read the value together with its context |
| `poor` | Acquisition compromised |
| `missing` | No valid value (`value: null`) |

`reasons` (optional): `motion`, `contact`, `not_received`, `out_of_sensor_range`.

**To decide together:** who computes the flag (device, backend or a dedicated pipeline) and with which method. In the demo the flag is assigned by the simulation scenario, which states it in `source.qualityMethod`. The frontend does **not** compute quality.

## Endpoints

### `GET /mission/status`
```json
{
  "simulated": true,
  "scenarioId": "session",
  "scenarioLabel": "Full session",
  "now": "2026-11-14T10:40:00Z",
  "link": { "state": "connected", "since": "2026-11-14T10:00:00Z", "lastContactAt": "2026-11-14T10:39:55Z" }
}
```
`link.state`: `connected` | `degraded` | `offline`. In production `scenarioId` and `scenarioLabel` may be omitted.

### `GET /crew`
```json
{ "items": [ { "id": "crew-a", "displayName": "Crew A", "note": "Pseudonymised identity — simulated data" } ] }
```

### `GET /crew/{crewId}/snapshot`
Latest state for the dashboard.
```json
{
  "crew": { "id": "crew-c", "displayName": "Crew C", "note": "…" },
  "activity": { "start": "2026-11-14T10:00:00Z", "end": "2026-11-14T10:45:00Z", "kind": "operational", "label": "Scheduled maintenance", "protocolId": "OPS-MANUT-45", "scheduled": true },
  "device": { "state": "not_reporting", "lastReceivedAt": "2026-11-14T10:22:00Z", "expectedIntervalS": 10 },
  "parameters": [
    {
      "parameter": "heart_rate",
      "latest": { "t": "2026-11-14T10:22:00Z", "value": 75, "quality": "good" },
      "lastValidSample": { "t": "2026-11-14T10:22:00Z", "value": 75, "quality": "good" }
    }
  ],
  "openEvents": 1
}
```
`device.state`: `streaming` | `delayed` | `not_reporting`. `activity` is `null` when no activity is in progress.

### `GET /crew/{crewId}/series?parameters=heart_rate,spo2&from=…&to=…`
```json
{
  "items": [
    {
      "crewId": "crew-b",
      "parameter": "spo2",
      "unit": "%",
      "receivedAt": "2026-11-14T10:40:00Z",
      "source": {
        "deviceId": "SIM-PPG-B",
        "deviceLabel": "Pulse oximeter (simulated)",
        "sensorType": "Photoplethysmography (PPG)",
        "placement": "Finger",
        "samplingIntervalS": 10,
        "processing": "Value aggregated over 10 s windows",
        "qualityMethod": "…",
        "firmware": "sim-0.1",
        "simulated": true
      },
      "samples": [
        { "t": "2026-11-14T10:18:00Z", "value": 92, "quality": "uncertain", "reasons": ["motion"] },
        { "t": "2026-11-14T10:18:10Z", "value": null, "quality": "missing", "reasons": ["not_received"] }
      ]
    }
  ]
}
```
- `samples` is sorted by ascending `t`.
- A sample that was not received may be omitted (a hole in the sequence) or sent as `missing`: the frontend handles both.
- Volume in the demo: 241 samples × 4 parameters per session. If the real rate is higher, we propose adding `resolution` (server-side aggregation) instead of sending raw data.
- `from` > `to` → `400`.

### `GET /crew/{crewId}/activities?from=…&to=…`
`{ "items": [ActivitySegment] }`. `kind`: `rest` | `warmup` | `exercise` | `recovery` | `operational`. `scheduled: true` = comes from the activity plan, not inferred from the data.

### `GET /crew/{crewId}/reference?parameter=heart_rate&protocolId=EX-CICLO-30`
Personal history for the same protocol. `404` when there is no history: the frontend treats it as an empty state.
```json
{
  "crewId": "crew-a",
  "parameter": "heart_rate",
  "protocolId": "EX-CICLO-30",
  "basis": "P10–P90 of good-quality samples from 5 previous sessions…",
  "sessions": [ { "id": "…", "date": "2026-11-04T10:00:00Z", "protocolId": "EX-CICLO-30", "mainPhaseMedian": 133, "goodQualityPct": 99.6 } ],
  "points": [ { "offsetS": 0, "low": 57.1, "median": 59.8, "high": 62.4 } ]
}
```
`offsetS` = seconds from the start of the protocol. **To decide:** minimum number of sessions, percentiles, and who defines the method. These are not clinical thresholds.

### `GET /events?crewId=&status=open,in_review`
`{ "items": [ReviewEvent] }`, sorted by `detectedAt` descending. Both filters are optional.

### `GET /events/{eventId}`
```json
{
  "id": "EV-0142",
  "crewId": "crew-a",
  "parameter": "heart_rate",
  "kind": "outside_personal_range",
  "detectedAt": "2026-11-14T10:15:30Z",
  "window": { "start": "2026-11-14T10:14:00Z", "end": "2026-11-14T10:20:10Z" },
  "status": "open",
  "trigger": { "ruleId": "DEMO-PR-01", "description": "Demo rule: …", "simulated": true },
  "annotations": []
}
```
- `kind`: `outside_personal_range` | `signal_quality` | `data_stale`.
- `parameter: null` = the event concerns the whole device feed.
- `trigger.description` is human-readable and shown to the user: **it must explain the rule without diagnostic language**.

### `PATCH /events/{eventId}` — `{ "status": "in_review" }`
`status`: `open` | `in_review` | `reviewed`. Returns the updated event.

### `POST /events/{eventId}/annotations` — `{ "text": "…" }`
Returns the updated event. The author must be derived from authentication, not from the client. Empty text → `400`. Maximum 2000 characters.

### `GET /crew/{crewId}/messages`
`{ "items": [CrewMessage] }`, most recent first.

### `POST /crew/{crewId}/messages` — `{ "templateId": "review_after", "relatedEventId": "EV-0142" }`
Predefined templates only (see `CREW_MESSAGE_TEMPLATES` in the frontend; the list should be served by the backend). No link → `503` with `code: "unavailable"`.

## Errors

```json
{ "error": { "code": "not_found", "message": "Event \"EV-9\" not found", "details": {} } }
```
| HTTP | `code` | Frontend behaviour |
|---|---|---|
| 400 / 422 | `bad_request` / `validation_error` | message next to the form |
| 401 / 403 | `unauthorized` | error message (authentication is not in the MVP) |
| 404 | `not_found` | “not available”; for `/reference` → empty state |
| 502 / 503 / 504 | `unavailable` | “service unreachable”; previous data stays visible with a notice |
| 5xx | `internal` | generic message |
| network failure | — | treated as `unavailable` |
| 2xx with a non-JSON body | — | treated as `internal` |

`message` is shown to the user: in English, without sensitive technical details.

## Open questions for backend and database

1. Real sampling rate and aggregation: who aggregates, and over which windows?
2. The quality flag: where does it come from, and with which validated method?
3. Events: rules on the backend? Who defines and approves them? (In the demo they are demo rules.)
4. Persistence of notes, statuses and messages; audit trail (who, when).
5. Updates: the frontend now **polls every 10 s** (configurable, paused while the tab is hidden). Is that acceptable for the backend load, or do we move to SSE/WebSocket later? An `ETag`/`If-None-Match` or a `since` parameter on `/series` would make polling cheaper.
6. CORS or development proxy (`vite.config.ts` → `server.proxy`).

## Hackathon autonomy flow — additional API endpoints / integration decisions

These endpoints are **already invoked by the frontend HTTP adapter** and need explicit agreement with the backend team:

| Method | Proposed endpoint | Purpose |
|---|---|---|
| `GET` | `/crew/{crewId}/daily-indicators` | Returns `{ "items": DailyIndicatorSeries[] }`, with quality, timestamp, source and personal (non-clinical) baseline |
| `GET` | `/crew/{crewId}/check-ins` | Returns `{ "items": CheckIn[] }` |
| `POST` | `/crew/{crewId}/check-ins` | Accepts 1–5 scores for sleep, energy and mood and optional note (≤500 chars) |
| `POST` | `/crew/{crewId}/reports` | Accepts `{ "note": string }`; creates an event of kind `crew_report` to be reviewed by the ground team |

**Not a backend implementation:** `frontend/src/state/crewLocal.ts` uses browser `localStorage` only when the source is mocked. It is not suitable for actual medical data. Offline outbox entries are removed only after the request succeeds. The demo mock persists delivered crew reports locally for cross-view review. A **real implementation** needs authenticated origin and permissions, encryption, retention rules, delivery acknowledgements, a retry strategy, server-side idempotency keys and an auditable received-at timestamp. The frontend should not claim delivery merely because a record was queued.

**Status of measurement rechecks:** Only a locally recorded task (`pending` / `acknowledged`) exists. No physical sensor command, validated recheck or clinical interpretation occurs. An actual sensor interface requires its own reviewed contract.

---

## Addendum — Daily indicators for the expanded crew UX (14 Nov 2026)

**Proposal only — not a claim that FastAPI endpoints already provide these values.**
The frontend now supports an **additive** extension of the existing
`GET /crew/{crewId}/daily-indicators` endpoint; no new endpoint or backend code
was implemented in this change. `items` may omit unsupported indicators. The UI
renders an explicit **Not supplied** placeholder and never fabricates missing
values when using the HTTP adapter. The standalone demo generates seeded,
synthetic data for these parameters.

Each `DailyIndicatorSeries` keeps the existing structure:
`crewId`, `indicator`, `unit`, `days` (array of `{date, missionDay, value,
quality}`), `baseline` (or `null`), `source`, `simulated`.

| Proposed `indicator` key | Unit | Example acquisition | Interview relevance |
|---|---|---|---|
| `resting_hr` | `bpm` | Resting ECG / chest sensor | Torchia, Ongaro |
| `resting_spo2` | `%` | Oximeter | Torchia |
| `resting_resp_rate` | `breaths/min` | Respiratory sensor; motion artifacts possible | De Vittorio, Torchia |
| `bp_systolic` | `mmHg` | Pressure cuff, paired with diastolic | Torchia, Ongaro |
| `bp_diastolic` | `mmHg` | Pressure cuff, paired with systolic | Torchia, Ongaro |
| `hrv_rmssd` | `ms RMSSD` | ECG-derived or validated PPG-derived estimate | Ongaro, Cerri (sleep/stress context) |
| `body_temperature` | `°C` | Thermometer | De Vittorio |
| `sleep_duration` | `h` | Wearable estimate | Cerri, De Vittorio, Ongaro |
| `sleep_efficiency` | `%` | Wearable estimate of time asleep / time in bed | Cerri, De Vittorio (research direction) |
| `activity_minutes` | `min` | Exercise equipment / activity log | Ongaro |
| `body_mass` | `kg` | Mission-approved mass measurement device | Ongaro |

**Important data distinctions:**
- `bp_systolic` and `bp_diastolic` represent **one paired cuff acquisition**.
  In the UI's simulated capture workflow the two values are saved together.
  Backend and hardware adapters must also preserve the pair, timestamp,
  acquisition context and quality status. A separate measurement-session ID
  is recommended for the production API.
- `hrv_rmssd` is an **estimate derived from an ECG/PPG acquisition**, not an
  independently measured disease marker. Its algorithms and signal quality
  need explicit validation before real use.
- `sleep_efficiency` is an **estimate**, not EEG-based sleep-stage analysis.
- Self-reported energy, sleep experience and mood remain in the **check-in**
  resource; they are not silently turned into physiological sensor data.
- EEG, immune status, bone mineral density, radiation exposure and laboratory
  biochemistry are **not inferred** from heart rate or sleep wearables. The UI
  explicitly identifies those gaps rather than inventing values.
- The demo's personal baseline is a *historical comparator*, **not a clinical
  normal range**. All quality labels are hypothetical demo metadata.

Example of two `DailyIndicatorSeries` records from one synthetic cuff capture:

```json
{
  "items": [
    {
      "crewId": "crew-a", "indicator": "bp_systolic", "unit": "mmHg",
      "days": [{ "date": "2026-11-14", "missionDay": 15, "value": 116, "quality": "good" }],
      "baseline": { "low": 109, "median": 115, "high": 121, "fromDay": 1, "toDay": 7,
                    "basis": "synthetic historical comparison, not a clinical threshold" },
      "source": "Synthetic demo cuff", "simulated": true
    },
    {
      "crewId": "crew-a", "indicator": "bp_diastolic", "unit": "mmHg",
      "days": [{ "date": "2026-11-14", "missionDay": 15, "value": 75, "quality": "good" }],
      "baseline": { "low": 70, "median": 75, "high": 80, "fromDay": 1, "toDay": 7,
                    "basis": "synthetic historical comparison, not a clinical threshold" },
      "source": "Synthetic demo cuff", "simulated": true
    }
  ]
}
```

**Before integrating with Andrea and Marco:** agree on exact identifiers and units;
which devices produce which values; assessment of quality at acquisition;
paired cuff transaction ID; freshness and baseline computation; and handling
unsupported metrics. A displayed React control is not evidence that a backend
endpoint or real device integration exists.

## Addendum — Sleep-aid schedule (PROPOSAL, 14 Nov 2026)

Purpose: each crew member plans the nights they intend to use a sleep aid, so the crew and the Flight Surgeon can check that at least one person stays without one every night (emergency readiness). **Only the plan is stored: no drug name, no dose, no advice.** The coverage rule is a demo setting (`SLEEP_COVER_RULE.minWithoutSleepAid = 1` in `frontend/src/domain/sleepPlan.ts`); the real rule must come from the mission's medical authority.

### `GET /sleep-aid-plan?from=2026-11-11&to=2026-11-24`
Planned nights for the whole crew, `from`/`to` inclusive (`YYYY-MM-DD`, UTC; the night that *starts* on that day).
```json
{ "items": [ { "crewId": "crew-a", "night": "2026-11-18", "updatedAt": "2026-11-14T10:40:00Z", "simulated": true } ] }
```
Only planned nights are listed (absence = not planned). `from > to` → `400`.

### `PUT /crew/{crewId}/sleep-aid-plan/{night}` — `{ "planned": true }`
Adds (`true`) or removes (`false`) the night. Returns the entries for that night: `{ "items": [ … ] }`. Past nights → `400`; unknown crew → `404`. The client asks for confirmation before a change that would leave nobody without a sleep aid, but the server should **not** silently refuse it: coordination is a human decision, and the Flight Surgeon sees uncovered nights.

### Open questions
- Who can see whose plan (whole crew vs. Flight Surgeon only)? Medication information is sensitive: decide with the medical team and record consent.
- Should the actual intake be logged (taken / not taken), or only the plan?
- The coverage rule (minimum crew members without a sleep aid) is configured where, and by whom?

## Addendum — crew data files (JSON profile + CSV measurements) · proposal

The team's data arrive as **one JSON file per crew member** (general profile) and **CSV files** (measurements). Until the real files are shared, the
prototype accepts the format below (`frontend/src/data/import/crewImport.ts`, tested) through **Demo → Import crew data (JSON + CSV)**. Files are parsed in
the browser and stored only in that browser. Samples with invented values: `docs/samples/`.

**Profile (JSON object).** All fields optional; common aliases are accepted.

| Field | Aliases | Use |
|---|---|---|
| `crewId` | `crew_id`, `id`, `astronautId` | Which crew member the data belong to (`crew-a`, `crew-b`, `crew-c` in the demo) |
| `displayName` | `name`, `callsign` | Name shown in the interface |
| `role` | `position` | Shown in the import preview |
| `missionStartDate` | `launchDate`, `mission_start_date` | Day 1 of the mission (YYYY-MM-DD); default 2026-10-31 |

**Measurements (CSV).** Two layouts are recognised automatically:

- *one row per day (wide)*: `date,resting_hr,sleep_duration,spo2,resp_rate,hrv,systolic,diastolic,temperature,activity_minutes,weight` — any subset, any
  order; optional `<column>_quality` columns;
- *one row per reading (long)*: `date,indicator,value[,unit][,quality]`.

Rules: date `YYYY-MM-DD` or `DD/MM/YYYY`, or a `mission_day` column; `,` or `;` separator (with `;`, decimal commas are read correctly); lines starting with
`#` are comments; quality is `good`, `uncertain`, `poor` or `missing` (default `good`). Days without a row stay **gaps** (never interpolated). Rows that
cannot be used are listed with their line number and skipped. The personal baseline needs at least 5 good readings in mission days 1–7.

Questions for the team: exact column names and units, one file per person or one per crew, time zone of the timestamps, and whether readings are daily
values or raw samples to aggregate.
