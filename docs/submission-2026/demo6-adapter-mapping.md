# Demo 6 integration specification

**Preparation only. No frontend change is made by this task.** Silvio is preparing
the matching React source. Preserve `OrbitVitals_Demo (6).html` as the authoritative
visual/interaction reference. Its inspected SHA-256 is
`e7503c35c970967d59f63e1b44b125d61a572ada51ca42130e8aa5c7eefe8f8b`.

## Source and design blockers

At the initial comparison, the fetched `origin/frontend-redesign-silvio` was
`c406bce`. Its published Today
implementation places an aggregate Health card and a sleep-plan card on the right;
the approved HTML instead contains six full metric tiles with sparklines and the
main selected trend chart on Today. The HTML also contains the Mission Day strip,
180-day simulated plan, Worth a look styling, richer chart interaction and 58 CSS
class names absent from the published stylesheet. It contains minified JavaScript
and CSS but no source map or original TypeScript source.

The current integration additionally swaps entire view trees in HTTP mode:
`CrewToday.tsx` selects `BackendCrewToday`, and `MedicalView.tsx` selects
`BackendMedicalView`. The preserved old CSS alone cannot make those different
trees match Demo 6. Those replacements are not an acceptable final architecture.

These static findings establish a source mismatch, not the exact authoring commit
or a completed pixel comparison. Obtain Silvio's exact source commit, package lock,
assets, styles, chart interactions, mission display metadata, workflow components
and offline build script. Do not reconstruct the dashboard from minified output
or infer missing behavior from an older branch.

## Crew identity mapping

This is a display mapping only. Backend IDs and names inside stored payloads do
not change. There is no crew directory endpoint.

| Demo 6 display | Scenario identity | Opaque backend ID   |
| -------------- | ----------------- | ------------------- |
| Crew A         | SIMULATED Vega    | `sim-mission-v1-01` |
| Crew B         | SIMULATED Noor    | `sim-mission-v1-02` |
| Crew C         | SIMULATED Chen    | `sim-mission-v1-03` |

Use the constant mapping rather than parsing IDs or renaming the seeder. Preserve
Crew A/B/C in the approved selector; show the scenario name and simulated notice
in an existing metadata/detail slot. Unknown identities must not fall back to Vega.

## Exact resource-to-view mapping

`createOrbitVitalsClient` and `loadDemoCrew` supply validated wire records;
`buildMetricView` and `buildNoorReplay` supply display selection. Use the existing
bridge rather than introducing another unvalidated HTTP client.

| Data needed                                           | Existing call and contract                                                      | Demo 6 consumer                                                                       |
| ----------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Service availability                                  | `GET /health` → `HealthResponse`                                                | Existing connection indicator, labelled as API reachability; no spacecraft link claim |
| Units/domains                                         | `GET /metrics` → `items: MetricDefinition[]`                                    | Card labels, axes, details and conversions                                            |
| Observations                                          | `GET /crew-members/{id}/measurements` → `items: PhysiologicalMeasurement[]`     | Latest-record cards, sparklines, charts, record details                               |
| Personal reference                                    | `GET /crew-members/{id}/baselines` → `items: PersonalBaseline[]`                | Reference state/statistics, reference window and eligible chart annotation            |
| Sleep results                                         | `GET /crew-members/{id}/evaluations?domain=sleep` → `items: EvaluationResult[]` | Worth a Look outcome, sleep evidence and Noor replay                                  |
| Activity results                                      | Same collection with `domain=physical_activity`                                 | Activity evidence; no invented daily-adherence endpoint                               |
| Mission schedule, check-ins, messages, sleep-aid plan | No resource                                                                     | Existing visual slots remain; mock behavior or explicit HTTP unavailable state        |

Paths are relative to the configured absolute `/api/v1` base URL. No
`/mission/status`, `/crew/.../snapshot`, `/series`, `/events`, `/messages`, `/rag`
or GET-by-evaluation-ID route is available. For an individual result, select the
exact opaque ID from the returned collection. Empty lists do not imply `nominal`.

## Six Today cards

These are the approved card slots, not new API field names. Actual metadata and
units remain intact. Missing observations keep their card and sparkline space.

| Demo 6 indicator                    | Canonical metric(s)                                   | Canonical unit | Seeded availability / display rule                                     |
| ----------------------------------- | ----------------------------------------------------- | -------------- | ---------------------------------------------------------------------- |
| `resting_hr`                        | `heart_rate`                                          | `bpm`          | Records available; resting/on-waking context is not a public field     |
| `sleep_duration`                    | `sleep_duration`                                      | `min`          | Records available; approved hours display is a presentation conversion |
| `resting_spo2`                      | `blood_oxygen_saturation`                             | `%`            | Records available; do not infer a resting context                      |
| `hrv_rmssd`                         | `heart_rate_variability_rmssd`                        | `ms`           | No seeded records; show unavailable, not mock HRV                      |
| `bp_systolic` plus paired diastolic | `systolic_blood_pressure`, `diastolic_blood_pressure` | `mmHg`         | No seeded records; both values unavailable, never 120/80 by default    |
| `resting_resp_rate`                 | `respiratory_rate`                                    | `breaths/min`  | Records available; resting context is unconfirmed                      |

For resting-specific labels, qualify available generic records as recorded values
with resting context unconfirmed in the existing metadata line. If that qualifier
cannot be presented clearly in the approved slot, keep that resting-specific value
unavailable until the acquisition context is supplied. A timestamp alone does not
prove posture, waking time or measurement conditions. Do not relabel generic data
as medically resting data to fill the layout.

Additional existing pages map `sleep_efficiency` → `sleep_efficiency` (%),
`activity_minutes` → `exercise_duration` (min), `body_temperature` →
`body_temperature` (degC), and `body_mass` → `body_mass` (kg). Catalog presence is
not record availability. Active energy is `active_energy_expenditure` in kcal;
never substitute it for exercise duration or a missing recovery score.

## Values, aggregates and units

The original last-night card consumes the latest eligible **measurement** at the
selected cutoff. A finding's `observed_value` is an **engine window aggregate**.
They are not interchangeable.

| Noor cutoff | Latest recorded night | Window median | Selected reference |
| ----------- | --------------------- | ------------- | ------------------ |
| 2 nights    | 475 min               | 482.5 min     | 480 min            |
| 5 nights    | 430 min               | 460 min       | 480 min            |
| 9 nights    | 370 min               | 430 min       | 480 min            |

To preserve the approved hours scale, divide sleep-duration presentation values,
reference statistics and duration deviations by 60. Keep the wire payload unchanged
in minutes. With the existing one-decimal display, the last nine-night record is
6.2 h; the window median is 7.2 h; the reference is 8.0 h. Show exact canonical
values in details/tooltips. Do not calculate deviations by subtracting rounded
labels. Efficiency deviations are percentage points; relative deviations are
dimensionless and must not be confused with those units.

## Chart and reference behavior

- Use actual timestamps and selected windows. Plot only `acceptable` observations;
  retain excluded records and notes in the existing evidence interaction. Preserve
  genuine zero values and visible gaps; do not interpolate, average conflicting
  records, invent daily totals or carry a value forward.
- Sleep uses the manifest's complete noon-to-noon UTC night buckets. Other metrics
  are raw observations unless an explicit existing aggregation defines otherwise.
  If a daily slot is ambiguous, show that uncertainty rather than inventing a mean.
- A finding's `baseline_id` selects the reference. No ID means no selected reference;
  a missing ID target means selected reference unavailable. Do not silently use the
  newest available baseline. Retain phase, window, count, status and provenance.
- A shaded reference interval must have an explicit descriptive meaning. If using
  actual `statistics.minimum`/`maximum`, label it as the observed reference range,
  not a clinical normal range. Do not manufacture median ± MAD thresholds or reuse
  the mock's reference policy as a backend conclusion.
- Keep the main resting-heart-rate chart in its approved location. Without resting
  context or a vital-sign evaluation, preserve its geometry and communicate the
  available recorded-data context or an unavailable state. Do not draw a new green
  health assessment from the chart.
- A Recovery panel has no backend recovery score. Retain its design; show only
  supported source data with its real meaning, or unavailable content. Do not
  infer recovery, fatigue or readiness from HRV, sleep, heart rate or activity.

## Separate scientific states

Preserve the original icon and badge locations with accurate labels. Keep the
canonical states alongside any visual glyph mapping.

| Contract state                                                  | Display meaning                                                                 |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Finding/evaluation `nominal`                                    | No configured signal; not a health clearance                                    |
| `attention`                                                     | Review suggested; not diagnosis or urgency                                      |
| `insufficient_data`                                             | Not enough data; no invented conclusion                                         |
| No finding/evaluation                                           | Not computed; distinct from a returned insufficient result                      |
| Quality `acceptable` / `degraded` / `unusable` / `not_assessed` | Checks passed / use with caution / not usable / not assessed                    |
| Baseline `established` / `provisional` / `insufficient_data`    | Reference ready / reference forming / no reference yet, under its stated policy |

For the old quality glyphs only: acceptable can use `good`, degraded `uncertain`,
unusable `poor`, and not-assessed `uncertain` with explicit text. A missing record
uses `missing`. This is a visual mapping, not a rewrite of `data_quality` or a
physiological status. Do not convert Noor's trend into `outside_personal_range`:
her baseline-deviation criterion is not met. The finding's explanation is the
authoritative reason, not the mock `evaluateIndicator`/`summarizeHealth` rules.

## Noor replay and Medical

Use `buildNoorReplay` to select the stored two-, five- and nine-night evaluations
by window end, not by array index or an ID parser. Clip measurements and complete
intervals to the selected horizon. A missing checkpoint shows unavailable content
in the same panel; it never reveals a later result. Duration/efficiency switches
retain the selected sleep checkpoint. Replay placement must be agreed in the
matching source rather than adding a technical dashboard.

The Medical sidebar, crew pane, event/evidence pane, charts and interaction flow
must remain the approved component structure. Adapt selected stored evaluations
into frontend presentation state; do not invent persisted `ReviewEvent` resources,
review status, annotations or messages. Render actual `summary`, finding
`explanation`, quality notes, `algorithm.name/version`, windows, phase and IDs as
escaped text. They are algorithm explanations, not live LLM output.

## Mission Day, workflow capabilities and errors

The API does not provide a mission epoch, a 180-day plan, live device freshness or
a mission phase timeline. Keep the approved controls and geometry, but use an
explicitly agreed simulation timeline or an unavailable value. Never shift the
October seeded observations to November to match the HTML's mock clock. The
original fixed mission-day clock is not evidence of backend mission time.

Mock and HTTP modes must use the **same Today and Medical components**. Change the
data/view-model provider and capability values, not the top-level dashboard tree.
Extend frontend-only presentation types after inspecting the matching source;
do not force canonical results into mock-only score semantics or alter schemas.

Retain Daily Review, check-in, device capture, sharing, annotations, messaging and
sleep-aid planning as functional simulations in mock mode. In HTTP mode, the final
implementation must retain their rows, panels and sheets with explicit
unavailable/read-only states. These are acceptance requirements, not a statement
that the current interface meets them. No simulated success toast or queued report
may imply that an absent endpoint was called.

Loading and HTTP/network errors occupy the approved visual states. Failed refresh
may retain the same crew member's last data with a stale notice. Changing crew or
mode must clear the previous selection while loading; superseded results cannot
replace it. A failed API never silently switches to mock mode.

## Handoff checklist

- [ ] Receive the exact matching source commit, assets, lockfile and build command.
- [ ] Confirm reference fixtures, viewport/theme/browser settings and interaction states.
- [ ] Agree mission-clock metadata and truthful handling of resting context.
- [ ] Use one component tree for both data sources; retain all approved card/panel slots.
- [ ] Connect existing bridge methods and the crew mapping above; preserve canonical payloads.
- [ ] Implement unavailable capabilities without deleting original visual structure.
- [ ] Pass [the acceptance specification](demo6-acceptance.feature), current tests and schema checks.
- [ ] Compare Today, Medical, charts, navigation and sheets at matching viewports.
- [ ] Obtain Silvio's visual acceptance and Marco's scientific-copy review.

The final React source, unified implementation and actual visual-regression results
are **pending**, not completed deliverables of this documentation task.
