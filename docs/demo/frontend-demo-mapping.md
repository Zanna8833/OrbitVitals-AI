# Frontend demonstration mapping

For Silvio. What each screen needs to show in the demonstration, where the data comes from, and
what does not exist yet. This maps the planned screens to the backend as it is; it does not
redesign the interface.

Backend state assessed: commit `667f512` (2026-11-14). All data is **simulated**.

## 1. What could and could not be verified

- No interface code is in this repository. `frontend/` contains only a placeholder README, which
  still describes a Flutter client. The screen names below come from the team's plan. Every
  interface behaviour in this document is therefore **proposed**, and each row says whether the
  data behind it exists.
- The backend behaviour quoted here was verified on 2026-11-14, through the scenario replay and
  through the real HTTP API. Field names follow [api-contracts.md](../api-contracts.md).

## 2. Five rules for the demonstration

1. **The astronaut is the user.** The challenge asks for a tool that "helps astronauts assess
   their own health". Open the demonstration on one crew member's own view. The crew overview is
   a doorway, and the flight surgeon is who the astronaut shares a finding with.
2. **Three lanes, never merged.** Data trust, personal reference and what changed are three
   separate answers with three separate badges. Do not combine them into one score or colour.
3. **Simulated, on every screen.** Keep a persistent "Simulated data, research prototype" label.
4. **Show the engine's words.** Display `summary` and `explanation` as returned. Add a plain
   headline above them; never replace them.
5. **Unknown is not zero and not green.** An empty list, a `null` value and `insufficient_data`
   each mean "not known". Render gaps as gaps.

## 3. The primary flow

Three views and two panels. About four clicks.

```text
Crew overview  ->  Astronaut view (three lanes + chart)
                      |-- "Why?"            -> Evidence panel (explanation, records used, settings)
                      |-- "Why it matters"  -> NASA Research Lens panel
                      |-- time slider       -> Decision Replay (2, 5, 9 nights)
                      '-- "What can I do?"  -> Action Center (next steps, share with flight surgeon)
```

Recommendation: implement Evidence, Research Lens and Action Center as panels or drawers of the
astronaut view, and Decision Replay as a slider on its chart. That keeps the story on one screen
and removes navigation from the 30-second cut.

## 4. Screen by screen

"Exists" refers to the data or API, not to the interface.

### Mission Control (crew overview). Priority P0, kept minimal

| Aspect | Specification |
| --- | --- |
| Purpose | Enter the system and pick a crew member. Five seconds of the demonstration |
| Information | Simulated crew name, mission phase, and per domain the latest evaluation status with its data-quality state |
| Source | `GET /crew-members/{id}/evaluations?domain=sleep&limit=1` and the same for `physical_activity` |
| Exists | Evaluations: yes. A list of crew members: **no endpoint**; use a constant in the frontend that matches the seeded identifiers. Mission phase: **no endpoint**; use the phase stored on the evaluation, or a constant timeline |
| Interaction | Select a crew member |
| Why it matters | Orientation only. It shows that two crew members can carry the same amber data badge for different reasons |
| Demonstration impact | Low. Do not linger |

### Astronaut Details (the astronaut's own view). Priority P0, the core screen

| Aspect | Specification |
| --- | --- |
| Purpose | Answer "how am I, and how sure is that?" for one indicator |
| Information | A time chart of the indicator; three lanes with one badge each; a plain headline; buttons for "Why?", "Why it matters" and "What can I do?" |
| Lane 1, data trust | `data_quality.status` of the finding, with completeness and flags. Per-record quality marks on the chart |
| Lane 2, personal reference | Status of the baseline used (`established`, `provisional`, `insufficient_data`), or "No reference yet" when the finding has no `baseline_id` |
| Lane 3, what changed | `findings[].status` for the metric, with `observed_value` and unit |
| Source | `GET /crew-members/{id}/measurements?metric=...`, `GET .../baselines`, `GET .../evaluations?domain=...` |
| Exists | Yes, all three |
| Interaction | Select a marked point to read its quality note. Switch between sleep duration and sleep efficiency |
| Why it matters | This is the challenge objective: the astronaut evaluates their own status |
| Demonstration impact | Highest. Most of the 30 seconds is spent here |

Chart rules: plot only records whose `data_quality.status` is `acceptable`. Show an `unusable`
record as a marker on the time axis with its note, not as a point at -30 or 125. Leave missing
nights as visible gaps. Do not draw a population average or a target line: a line near the data
would look like a threshold, and the system has none.

### Evidence Explorer. Priority P0, as a panel

| Aspect | Specification |
| --- | --- |
| Purpose | Show how the result was reached |
| Information | The `explanation` of the finding, split into sentences; algorithm name and version; evaluated window; data-quality `notes`; the screening settings; the baseline identifier when one was used |
| Source | `EvaluationResult.findings[].explanation`, `.data_quality.notes`, `.algorithm`, `.window_start`, `.window_end`, `.summary` (the sleep policy is serialised after "Policy:") |
| Exists | Yes |
| Interaction | Expand "How was this decided?"; expand "Settings used" |
| Why it matters | Explainability and reproducibility, the basis of our Validity argument |
| Demonstration impact | High for technical judges; a two-second glance in the short cut |

Splitting the explanation on sentence boundaries is formatting and is safe. Extracting numbers
from it is fragile; see section 5.

### Decision Replay. Priority P0 for Scene B

| Aspect | Specification |
| --- | --- |
| Purpose | Show the same question asked after 2, 5 and 9 nights |
| Information | For each checkpoint: nights used, status, data quality, and the chart revealed up to that moment |
| Source | Three stored sleep evaluations with different `window_end`, returned newest first by `GET .../evaluations?domain=sleep`; or the `steps` array of the replay output |
| Exists | Yes, if the seeding step stores the three evaluations. To be confirmed with the author of the seeder. The replay output always contains them |
| Interaction | A three-position slider or step buttons |
| Why it matters | It makes longitudinal reasoning visible, including the refusal to judge after two nights |
| Demonstration impact | Highest per unit of effort. This is the moment people remember |

Expected values at each position are in
[primary-demo-flow.md](primary-demo-flow.md#the-same-question-asked-at-three-moments).

### NASA Research Lens. Priority P0, as a panel

| Aspect | Specification |
| --- | --- |
| Purpose | Answer "why is this measured in space, and what does NASA say about it?" |
| Information | For the current indicator: the NASA risk name, NASA's description quoted verbatim, what NASA says can be done, a link, and one line of published context |
| Source | Static content in the frontend, taken from [scientific-evidence-matrix.md, section 4](scientific-evidence-matrix.md#4-nasa-hazards-and-risks-behind-each-indicator) |
| Exists | The content is prepared. There is no API: the RAG module is a placeholder |
| Interaction | Open from "Why it matters" |
| Why it matters | The Relevance criterion asks for NASA data as "a core component". This is where NASA material becomes part of the product |
| Demonstration impact | High. Show it in every cut, even for two seconds |

Label the panel "NASA resource, for context. Not used by the algorithm." That sentence is true
and protects us from the question "is this NASA data in your computation?".

### Action Center and Reports. Priority P0, minimal

| Aspect | Specification |
| --- | --- |
| Purpose | Turn a finding into a next step |
| Information | Two or three follow-up cards chosen by the kind of finding, and a generated summary for the flight surgeon |
| Source | Static card text (section 6) plus the fields of the evaluation |
| Exists | **No backend support.** Everything is client-side |
| Interaction | "Share with flight surgeon" builds a text summary to copy or print. "Acknowledge" stores local state |
| Why it matters | The challenge asks that astronauts "act on the status of their health" |
| Demonstration impact | High. It closes the story |

### Investigation Workspace. Priority P2

| Aspect | Specification |
| --- | --- |
| Purpose | Look at several indicators side by side |
| Information | Sleep and exercise charts for the same period |
| Source | `GET .../measurements` for several metrics |
| Exists | The data exists. No cross-domain algorithm exists |
| Why it matters | Limited for this demonstration |
| Recommendation | Leave it out of every cut. If shown, present charts only and state no relationship between indicators |

## 5. Data sources and what is missing

### Implemented endpoints the demonstration uses

| Call | Used for |
| --- | --- |
| `GET /health` | A small connection indicator |
| `GET /metrics` | Metric names, units and domains. Do not hard-code units |
| `GET /crew-members/{id}/measurements` | Charts and per-record quality |
| `GET /crew-members/{id}/baselines` | Lane 2 |
| `GET /crew-members/{id}/evaluations` | Lane 3, Evidence, Decision Replay |
| `POST /measurements`, `POST .../baselines`, `POST .../evaluations` | Seeding. Best done by the seeding script, so that the interface only reads |

A read-only interface over a seeded backend is the simplest reliable arrangement. Agree the crew
identifiers, the evaluation windows and the three checkpoints with the author of the seeder.

### Not available, with a workaround

| Need | State | Workaround for the demonstration |
| --- | --- | --- |
| List of crew members | No endpoint (open point 4 in the contract) | Constant in the frontend |
| Mission timeline | `GET /missions/{id}/phases` is proposed, not implemented | Use `mission_phase` on each evaluation and baseline |
| Follow-up actions | Nothing | Static cards (section 6) |
| NASA evidence | Nothing; RAG is a placeholder | Static content |
| Trend numbers as fields (slope, fitted change, missing nights, signal name) | Present only inside the `explanation` text over HTTP. Structured in the replay output under `outputs.sleep_trends` | Show the explanation as text. If a number is needed in a headline, read it from the replay output |
| Vital-signs and cognition evaluations | Not reachable: a `vital_signs` request returns 422; cognition has no API | Do not show as live results. At most an "In development" note |
| Report export | Nothing | Client-side text summary |

### Two ways to feed the interface

| | Live API | Replay output as a fixture |
| --- | --- | --- |
| How | Seed, then read with the calls above | Capture `python -m app.scenarios replay <id> --json --validate` to a file and load it |
| Strength | Shows a real running system | Deterministic, offline, and includes structured trend numbers and all three checkpoints |
| Weakness | Data disappears when the server restarts | Not a public API shape; fields differ slightly (see the table in [primary-demo-flow.md](primary-demo-flow.md#8-reproducing-the-outputs)) |
| Use | First choice | Fallback for recording, and the source for headline numbers |

If the fixture route is used, say so on screen: "Precomputed by the OrbitVitals engines;
reproducible with one command."

## 6. Follow-up actions

The minimum set that makes outputs actionable without prescribing anything. All of it is
proposed interface behaviour.

### Which cards to show

| Finding | Condition in the data | Cards |
| --- | --- | --- |
| Measurement problem | Any record `unusable`, or flags `signal_artifact`, `duplicate`, `out_of_sensor_range` | Fix the measurement |
| Incomplete record | Flag `missing_data`, or completeness below 1 | Complete the record |
| Review suggested | Finding `status` is `attention` | Understand the risk; Share with flight surgeon |
| Not enough data | Finding `status` is `insufficient_data` | Complete the record |

A finding can show several cards. Scene B shows three.

### Card text

| Card | Text | Basis |
| --- | --- | --- |
| Fix the measurement | "Some records could not be used. Check the device and its connection, then record again if you can. No health conclusion was drawn from these records." Followed by the quality notes of the affected records | Our wording; the notes come from the engine |
| Complete the record | "These nights are missing: {dates}. If you know them, add them. The result becomes more reliable with a complete record." | Our wording; dates from the explanation or the replay output |
| Understand the risk | The NASA Research Lens content for the indicator, including "what NASA says can be done", quoted | NASA pages, verbatim |
| Share with flight surgeon | "This is a screening result, not a diagnosis. Your flight surgeon can interpret it with the full context." Button: build summary | Our wording |

The summary for the flight surgeon should contain: crew identifier, indicator, status, window,
data quality with flags, the full explanation, algorithm name and version, and the line
"Simulated data. Research prototype. Not a diagnosis."

### Limits to respect

- No medication, dosage, treatment or exercise prescription, and no urgency level.
- NASA's countermeasure sentences are shown as quotations about what NASA does, not as
  instructions to the user.
- Do not attempt live re-recording in the demonstration without testing it first. A second
  record for the same observation time and device with a different value makes **both**
  `unusable` (the engine treats them as conflicting copies). New records also invalidate stored
  evaluations for that period, which must then be recomputed.
- Any value typed during a demonstration is fabricated and must be sent with
  `source: "simulated"`.

## 7. Status labels

Suggested display text. Keep the API value available in a tooltip or in the Evidence panel.

| Field | API value | Display text |
| --- | --- | --- |
| Finding or evaluation `status` | `attention` | Review suggested |
| | `nominal` | No configured signal |
| | `insufficient_data` | Not enough data |
| | `alert` | Not produced by any current engine. Do not display it in the demonstration |
| `data_quality.status` | `acceptable` | Checks passed |
| | `degraded` | Use with caution |
| | `unusable` | Not usable |
| | `not_assessed` | Not assessed |
| Baseline `status` | `established` | Reference ready |
| | `provisional` | Reference forming |
| | `insufficient_data` or no baseline | No reference yet |

Visual guidance:

- Give the data-trust lane a different visual language from the health lane, for example an icon
  set or outline style, so that an "unusable" record cannot be read as a health emergency.
- Do not use green for `nominal`. It reads as "healthy", which the engine explicitly does not
  claim. A neutral colour with the text is safer.
- Do not rely on colour alone. Every badge carries its text.

### Plain headlines

The engine's explanations are precise but written for engineers ("Theil-Sen slope=-15 min/day;
decreasing transition fraction=1"). The challenge reminds teams not to "assume that astronauts
know everything". Put one plain sentence above the technical text.

| Situation | Headline |
| --- | --- |
| Sleep duration, `attention`, explanation contains `progressive_duration_reduction` | "Your recorded sleep has been getting shorter. Review suggested." |
| Any metric, `nominal` | "No pattern was found with the current settings. This does not mean everything is fine." |
| Any metric, `insufficient_data` | "There is not enough reliable data to tell yet." |
| Records `unusable` | "Some measurements could not be used." |

Matching the token `progressive_duration_reduction` in the explanation is acceptable for the
demonstration. A structured field would need a contract change, which is a whole-team decision
for after the hackathon.

## 8. Reliability checklist for recording and judging

- Start the backend with one worker and without `--reload`. A restart erases every record.
- Set `ORBITVITALS_DATA_QUALITY` with the daily sampling interval before starting, as shown in
  [primary-demo-flow.md](primary-demo-flow.md#8-reproducing-the-outputs).
- Seed immediately after every start. Show the result of `GET /health` somewhere small.
- Treat `{"items": []}` as "nothing computed yet". Never as `nominal`.
- Use fixed `evaluated_at` values when seeding, so that results are identical on every run.
- Record a backup screen capture as soon as the primary flow works once.
- Keep the replay output file in the frontend as an offline fallback.
- All interface text in English. No NASA logo or insignia in generated graphics.
- If the interface is published on a new website, the Submission Guide suggests requesting a web
  filter classification so that judges can open it.
