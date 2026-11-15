# OrbitVitals AI — Frontend (prototype)

> **Demo prototype for the NASA Space Apps Challenge. All data is simulated.**
> Not a medical device: no diagnosis, no clinical guidance. Not connected to, endorsed by or used by NASA or ESA.

OrbitVitals helps the people who look at physiological data in space understand **whether** a measurement can be trusted, **when** it was acquired and **in what context**. The astronaut sees only what matters to them; the Flight Surgeon gets the evidence needed to review an item. The rationale is in [`docs/UX_ANALYSIS.md`](docs/UX_ANALYSIS.md). The interface design and the reasons behind it are in [`docs/DESIGN.md`](docs/DESIGN.md).

## Try the demo (no install)

Open **`OrbitVitals_Demo.html`** (build it with `npm run demo` in this folder) in Chrome, Edge, Safari or Firefox. It is a single self-contained file with no server and no network access.

Suggested walkthrough (3 minutes):

1. **Crew · Today** (Crew A). The *Now* card shows the activity in progress. The summary card reports that resting heart rate has been higher than usual for 4 days; its trend against the personal usual range is already shown on the right. Select another tile to change the trend.
2. **Daily review**:
   - do the check-in;
   - take a simulated blood-pressure measurement;
   - share with the medical team.
3. **Medical**. The shared report appears at the top of *Review*. Open *Value outside personal historical range* and look at the chart, the observed figures and the provenance. Then set *In review*, add a note and send *“After the activity, please check the placement…”*.
4. Back in **Crew**, the request now appears in the *Now* card.
5. **Sleep plan**: the *Sleep plan* row on Today warns that on *Wed 18* every crew member planned a sleep aid. Open it: the *Next morning* row shows the (simulated) spacewalk and docking; the side card offers *Move mine to Thu 19*. Switch *Viewing as* to Crew B and tap *Sun 15* (spacewalk next morning): the sheet proposes another night. In **Medical**, the sidebar shows the uncovered nights.
6. **Import data**: *Demo → Import crew data (JSON + CSV)* → *Use the sample files* → *Import*. Today now shows *Imported data* and the trend computed from the CSV (format in `docs/FRONTEND_DATA_CONTRACT.md`).
7. **Demo ▾ → Long mission · Changed trend + no ground link**. Share again: the report is saved on the device. Switch back to *Full session*: it is delivered.

The **Demo** menu also holds the other scenarios (consistent data, uncertain quality, data not updated, no connection, event to review), *Live replay* from 10:30 UTC, auto-refresh, appearance (Auto / Light / Dark) and *Reset demo data*.

**For judges:** under every trend, the three pillars (**data quality**, **personal baseline**, **trend**) show how far a number can be trusted, how it compares with the person's own usual range and why a change deserves attention; the ⓘ explains each method. The footer link *What is real, what is simulated?* lists what works and what is simulated in this prototype.

## Getting started (development)

Requirements: Node.js ≥ 20.

```bash
cd frontend
npm ci               # exact versions from package-lock.json
npm run dev          # http://localhost:5173
```

On Windows, prefer `npm ci` to `npm install`: `npm install` can rewrite `package-lock.json` and drop platform-specific packages that teammates on Linux/macOS need.

| Command | What it does |
|---|---|
| `npm run dev` | development server |
| `npm run build` | type-check (`tsc -b`) + production build in `dist/` |
| `npm run demo` | production build + regenerates `OrbitVitals_Demo.html` in this folder |
| `npm test` | unit and contract tests (Vitest) |
| `npm run lint` | lint (oxlint) |

The only runtime dependencies are React and React DOM. Charts and routing are hand-written (SVG and a hash router).

## What works

| Area | URL | Content |
|---|---|---|
| **Crew · Today** | `#/crew/crew-a` | One screen, no scrolling. Left: *Now* (only during a scheduled activity), one summary card, *Daily review*. Right: *Your health* tiles and the trend of the selected one (*All indicators* opens the Health page). *Daily review* includes the crew **Sleep plan** (badge when a night is uncovered). Check-in, measurement, sharing and details open as sheets. |
| **Crew · Health** | `#/crew/crew-a/health` | All 10 daily indicators and the trend of the selected one against the personal usual range. |
| **Crew · Sleep plan** | `#/crew/crew-a/sleep` | Two-week calendar of planned sleep-aid nights for the whole crew; each member edits their own row; shows next-morning activities (simulated), who stays ready, and a one-tap fix for nights without cover; a confirmation with an alternative night appears before a night would be left without anyone free of a sleep aid or before your own activity. Only the plan is recorded (no drug, no dose). |
| **Assistant (slot)** | `#/assistant` | Placeholder page for the team's language-model assistant, reached from the small *Assistant* bubble in the footer. Not connected: no prompt is sent anywhere. |
| **Medical · Sleep-aid plan** | `#/medical/sleep` | The same calendar, read-only, for all crew, with the list of nights without cover (badge in the sidebar). |
| **Medical · Review** | `#/medical` | Split view. The list on the left shows items to review and the crew with data freshness. The selected **event** (`#/medical/event/EV-0142`) shows why it is here, one main chart (±5 min or the whole session; *Compare signals* shows all four), observed figures computed from the samples, context and provenance, and *Your review* (status, notes, predefined message). A **crew member** (`#/medical/crew/crew-a`) shows latest values with quality, the current session and the day-to-day indicators that changed. |

On a laptop or desktop screen (from 1024 × 620) **every view fits the window without scrolling**; phones keep a normal scrolling page. Older links (`#/surgeon`, `#/events/…`, `#/crew/…/health`) still work.

**Auto-refresh.** Every 10 s (`VITE_REFRESH_INTERVAL_S`, `0` = off). It pauses while the tab is hidden and can be paused from the Demo menu. If a refresh fails, the last data stays visible with an explicit notice. The nav bar always shows the ground link status and the simulated time.

**Colour and accessibility.** One tint colour for actions. Category colours (heart, respiration, rest, activity, body) appear only on labels and trends. Orange marks “attention”; red is never used, so nothing reads as an alarm. Sample quality uses distinct shapes as well as colours (● good, ◐ uncertain, ▲ poor, dashed ○ missing). Sheets are native `<dialog>` elements (focus trap, Esc). Charts are focusable, with arrow keys, a data table and screen-reader summaries. Light and dark themes are supported. The layout is checked at 390 px with no horizontal scroll.

## Simulated data

- Generated **deterministically** (`src/data/mock/`): the same values on every run.
- Session phases: 14 Nov 2026, 10:00–10:40 simulated UTC, one sample every 10 s, three pseudonymous crew members.
- Personal history: 5 previous sessions, also simulated.
- **Also simulated:**
  - the quality flags;
  - the rules that generate events (`DEMO-*`);
  - the device and processing descriptions;
  - the update thresholds (60 s / 5 min).

  None of these is a validated method or a clinical threshold.
- Daily crew check-ins, simulated measurements, shared crew reports and outgoing queued reports are persisted in this browser's `localStorage` in the **mock demo only**, to demonstrate a disrupted link and later synchronization. On environments that block local storage, they remain session-only.
- Surgeon-created annotations and outbound ground messages remain in memory. This is **not a secure store** and cannot be used for real personal health data; shared reports are delivered only to the simulated browser-local medical inbox, not to a real server.

## Backend integration

1. Agree on [`docs/FRONTEND_DATA_CONTRACT.md`](docs/FRONTEND_DATA_CONTRACT.md). It is a **proposal**: see “Open questions” at the end of the document.
2. Run the frontend against the backend:
   ```bash
   VITE_DATA_SOURCE=http VITE_API_BASE_URL=http://localhost:8000/api/v1 npm run dev
   ```
   See `.env.example`. Alternatively, configure `server.proxy` in `vite.config.ts` to avoid CORS issues.
3. Views depend only on the `DataSource` interface (`src/data/DataSource.ts`). `HttpDataSource` implements the contract endpoints and is covered by **contract tests with a fake `fetch`** (`HttpDataSource.test.ts`). It has **not yet been run against a real server**.

Still missing for the integration:

- authentication and roles;
- secure, server-authoritative persistence, audit trail and replay protection/idempotency for reports, notes and statuses;
- secure encrypted at-rest/offline outbox for any real health data (the `localStorage` queue is demo-only);
- message templates served by the backend;
- end-to-end integration tests against the real backend;
- optionally, server push (SSE) instead of polling.

## Limits of the demo

- It is a **design hypothesis**, not proof that current NASA/ESA tools are inadequate: the interviews do not show that (see `docs/UX_ANALYSIS.md` §7).
- Two narrowly bounded scenarios: scheduled physical activity (Flight Surgeon) and daily self-review on a simulated long mission (crew). The measurement flow is **simulated**: the browser does not acquire a real sensor reading.
- Connectivity loss/reconnection is a **simulation**: queue and simulated ground inbox live in one browser, not across real devices or a spacecraft link.
- Radiation, bone and muscle loss, immunological biomarkers and clinical behavioural-health assessments are outside the current demo.
- The quality flags and the personal historical range have no scientific validation.
- No artificial-intelligence feature is implemented. This is deliberate: no evidence calls for one in this MVP.
- No testing with real users yet.

## Sources, datasets and tools to declare in the submission

- **UX research:** synthesis of interviews with M. Cerri, D. Simeone, M. De Vittorio, P. Carlucci, L. Paciucci, F. Torchia, F. Ongaro (`docs/research/`, in Italian; an English summary is in `docs/UX_ANALYSIS.md`). Sharing the recordings requires the participants’ consent.
- **Data:** synthetic only, generated by the code in this repository. No NASA or public dataset is currently used.
- **Potentially relevant public datasets:** **to be checked** for content, licence and terms of use before any use, and to be kept separate from the synthetic data. Candidates:
  - NASA Open Science Data Repository (OSDR);
  - NASA Life Sciences Data Archive (LSDA), access on request;
  - PPG/ECG during exercise datasets on PhysioNet, useful for motion artifacts but not space-specific.
- **AI tools:** part of the UX analysis, the frontend code and the documentation was produced with the assistance of **Claude (Anthropic) via Claude Code**, under the team’s review. To be declared according to the Challenge rules.
- **Challenge:** see [`docs/SUBMISSION.md`](docs/SUBMISSION.md). Search results quoting the official guides indicate: deadline Sunday 15 Nov 2026, 11:59 p.m. local time; English required; AI tools allowed but their use must be described; all external resources listed in References. The official site could not be opened from the development machine, so the team must confirm these points and read the official challenge statement.

## Structure

```
OrbitVitals_Demo.html  standalone demo (generated by `npm run demo`)
docs/
  DESIGN.md                  interface design: architecture, visual system, verification
  UX_ANALYSIS.md             problem, users, scenarios, MVP, hypotheses
  FRONTEND_DATA_CONTRACT.md  data the frontend expects + JSON/CSV import format (proposal)
  SUBMISSION.md · samples/
tools/build-offline.cjs      inlines the production build into one HTML file
src/
  domain/              types and pure functions (quality, freshness, gaps, history, crew health)
  data/                DataSource · mock/ · http/
  state/               app state, auto-refresh poller, demo-only local storage
  hooks/               useQuery, useMutation, hash router
  components/          ui.tsx (Sheet, Segmented, List/Row), NavBar, charts, glyphs
  views/crew/          CrewToday + Sheets
  views/medical/       MedicalView (split view) · EventPane · CrewPane
```
