# OrbitVitals AI — UX analysis and MVP definition

Team working document, November 2026. Primary source: `docs/research/OrbitVitals_AI_Riepilogo_Interviste_UX.pdf` (in Italian; synthesis of 6 sessions with 7 professionals).

Every statement is labelled:

- **[E] Evidence collected**: reported in the interview synthesis. I state who expressed it.
- **[I] Design interpretation**: a choice of ours derived from the evidence.
- **[H] Hypothesis to verify**: not supported by the interviews; it must be validated.

> Limit stated in the source: no testimony constitutes a usability test of the NASA/ESA software in use in 2026. Part of the experience is historical (Ongaro: ESA experience ended in 2007). Other parts concern research prototypes (De Vittorio) or a suborbital mission (Carlucci/Paciucci). This document does **not** claim that current tools are inadequate.

## 1. Problem statement

In remote health monitoring, the person reviewing the data (Flight Surgeon or supervisor) may need to:

- tell a physiological change apart from an uncertain measurement;
- understand its trend and context;
- decide which approved check or procedure to consult.

They must be able to do this without being overwhelmed by raw data. The person busy with the activity (the astronaut) only needs to know whether data collection is working and whether someone is asking them something.

- The wording is the same as §5 of the synthesis. It remains **[H]**: a candidate problem, not a demonstrated gap.
- The interviews converge on the relevance of each link in the chain **[E]**: measure well → understand the data → present it in relation to the task → assess.

## 2. Primary users and needs

| User | Need | Basis |
|---|---|---|
| Flight Surgeon / supervisor on the ground | Understand whether an anomaly is real and which decisions are possible | [E] Ongaro |
| | Recognise noise, artifacts and uncertain measurements; not trust data just because it looks “clean” | [E] Simeone, Torchia |
| | Read the data in the context of mission, activity and person | [E] Cerri |
| | A richer view, with interpretable results and reports | [E] De Vittorio (interface for physicians distinct from the one for researchers) |
| Astronaut during an activity | Few elements, no overload, selective and understandable notifications | [E] Carlucci/Paciucci, Torchia |
| | Know whether data is up to date or unavailable | [I] from Carlucci/Paciucci (who receives the alert) and Cerri (trust, transparency) |
| On-board Medical Officer (distant missions) | Consult information without immediate support from Earth | [E] Ongaro (perspective). **Out of the MVP** [I] |
| Researcher / developer | Control of acquisition and raw signals | [E] De Vittorio. **Out of the MVP** [I] |

## 3. Use scenario (single scenario for the MVP)

An astronaut performs a scheduled physical activity: cycle ergometer, demo protocol `EX-CICLO-30` with rest, warm-up, constant load and recovery phases. The system receives simulated physiological data. At some point a measurement appears that needs to be checked.

The synthesis (§6) recommends starting from a single, limited decision scenario. The MVP covers five demo variants of it:

| # | Variant | Who sees it | What it demonstrates |
|---|---|---|---|
| 1 | Data available and consistent | everyone | The “nominal” condition is recognisable without visual noise |
| 2 | Uncertain quality (Crew B, SpO₂) | Surgeon, then Crew | Telling an uncertain measurement apart from a physiological change [E Simeone] |
| 3 | Data not updated (Crew C) | Surgeon, Crew | An old value must not look current |
| 4 | No connection | Surgeon, Crew | The system state is always explicit |
| 5 | Event to review (Crew A, HR) | Surgeon | Comparison with personal history, not with clinical thresholds [E Cerri, I] |

### Flight Surgeon flow

1. **Dashboard.** For each crew member: update status, latest value with its quality, and number of open events.
2. **Events.** List of events to review, each with the reason it was flagged.
3. **Event detail**, which contains:
   - the parameter trend, with the event window and personal history;
   - parameters recorded at the same time, including motion as a context signal;
   - **observed data**, i.e. computed facts;
   - activity context and data provenance;
   - **interpretation**, i.e. notes written by people;
   - review status;
   - an optional predefined message to the crew.
4. **Back to the dashboard.** The event is now “In review” or “Reviewed”.

Data reloads automatically (every 10 s in the demo); the Flight Surgeon can pause it to review a fixed snapshot **[I]**.

### Astronaut flow

A single view, without charts, ordered by the questions the astronaut has:

- **what to do now** — by default nothing (“carry on with your activity”); an action appears only when a person on the medical team asks for it, is always for *after* the activity, and names the sensor concerned **[I]**;
- where they are in the activity plan (phase track, time left);
- data collection and sensor status in plain language;
- messages from the medical team.

Numerical values are available only on request, in a section that is collapsed by default.

## 4. Essential user stories

1. As a **Flight Surgeon**, I want to see for each member when the latest data arrived, so that I do not mistake an old value for a current one.
2. As a Flight Surgeon, I want to see the quality of every sample next to its value, so that I can tell an artifact from a physiological change. *[E Simeone, Torchia]*
3. As a Flight Surgeon, I want to compare the value with previous sessions of the same person and the same protocol, so that I can assess it in context. *[E Cerri]*
4. As a Flight Surgeon, I want to see the current activity on the same time axis as the data. *[E Cerri, Ongaro]*
5. As a Flight Surgeon, I want to know why an event was flagged and which device and processing the data comes from. *[I from Simeone: “filtering can compromise information”]*
6. As a Flight Surgeon, I want to keep observed facts separate from my interpretation and record the outcome of the review. *[I from §6 “avoid an isolated value looking like a diagnosis”]*
7. As an **astronaut**, I want to know at a glance whether data collection is working, without reading parameters. *[E Carlucci/Paciucci]*
8. As an astronaut, I want to receive only short, non-urgent messages that do not interrupt the activity. *[E Torchia, Carlucci/Paciucci]*

## 5. Priority MVP features

| Feature | Evidence | Type |
|---|---|---|
| Update indicator (“Current / Delayed / Not updated”) with UTC time and data age | Ongaro: transmission did not seem the central problem to him, but an old value read as current leads to wrong assessments | [I] |
| Per-sample quality: glyph, label and strip below the chart; reasons for the flag | Simeone, Torchia, De Vittorio (artifacts, sensor–skin contact) | [E]→[I] |
| Visible data gaps (hatched “No data”, no interpolation) | Simeone (clean-looking data is not automatically correct) | [I] |
| Personal historical range (P10–P90 of previous sessions of the same protocol) instead of clinical thresholds | Cerri (context of the person and the mission) | [I]; usefulness [H] |
| Scheduled activity strip on the time axis | Cerri, Ongaro (monitored physical activity) | [E]→[I] |
| Aligned charts with a shared cursor, including motion | Simeone (motion → artifacts) | [I] |
| Event detail: *observed data* separate from *interpretation* | Synthesis §6, “no diagnosis” boundary | [I] |
| Data provenance (device, sensor, placement, processing, reception) | Simeone, De Vittorio | [I] |
| Reduced crew view, with no charts or thresholds | Carlucci/Paciucci, Torchia | [E]→[I] |
| Predefined, non-clinical messages from the Surgeon to the crew | Torchia (selective notifications), Cerri (trust) | [I]; template wording [H] |
| Link status always visible; explicit banner when lost | Synthesis §4 (divergence on transmission to be preserved) | [I] |
| Auto-refresh with pause, and an explicit notice when a refresh fails | Old data must never look current (see the update indicator) | [I] |

## 6. Excluded features (and why)

- **Diagnosis, risk scores, clinical thresholds, emergency alarms.** Ruled out by the design boundary, and we have no clinical validation.
- **“AI” component (anomaly detection, predictions).** Not required by any evidence. Introducing it now would produce unverifiable reliability. The project name is not a sufficient reason.
- **Dashboard with every parameter in real time.** Explicitly discouraged by the synthesis (§6, §8).
- **Distant-mission mode, on-board autonomy, communication delays.** This is the “third level”: it needs specific confirmation.
- **Researcher interface with raw signals.** A different user [E De Vittorio].
- **Free text to the crew, sound notifications, modal pop-ups.** Risk of cognitive load.
- **Real authentication and roles.** The view selector is for the demo only.

## 7. Risks and unvalidated hypotheses

| # | Hypothesis or risk | How to verify it |
|---|---|---|
| H1 | The Flight Surgeon is the user with the most frequent difficulty (rather than the supervisor or the on-board Medical Officer) | Structured interviews (synthesis §7, “priority user”) |
| H2 | Tools in use do not already offer per-sample quality, trends and personal history | Benchmark (synthesis §7) — **not done yet** |
| H3 | The personal historical range is a more useful reference than fixed thresholds | Tests with physicians on simulated cases |
| H4 | Motion as a context signal helps recognise artifacts without leading to hasty conclusions | Think-aloud test on the event detail |
| H5 | The astronaut prefers not to see their own values during the activity | Questionnaire or test with Earth analogues; this is why the values are in a collapsed section |
| H6 | The message templates are acceptable and do not cause anxiety | Review with aerospace medicine experts |
| R1 | Quality indicators are simulated: a real indicator needs a validated method from the acquisition chain | To agree with the backend and with experts |
| R2 | A convincing demo could be read as proof of a need: it must be presented as a hypothesis | Wording of the demo and the submission |
| R3 | A real episode in which the interface was the limiting factor is not yet documented (synthesis §7) | Search for a verifiable case |

## 8. Frontend structure

```
frontend/src/
  config.ts    build-time configuration (data source, API base URL, refresh interval)
  domain/      types, labels, pure functions (freshness, gaps, statistics, history comparison, crew status)
  data/        DataSource (interface) · mock/ (deterministic generator, scenarios) · http/ (API adapter + contract tests)
  state/       scenario, current data source, revision, auto-refresh poller
  hooks/       useQuery (loading/error/refresh without flashes), useMutation, minimal hash router
  components/  TimeSeriesChart (SVG), status glyphs, header, empty/error states
  views/       surgeon/ · event/ · CrewView
```
