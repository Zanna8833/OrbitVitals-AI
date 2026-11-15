# OrbitVitals — Web platform

OrbitVitals helps the crew and the medical team read physiological data in space: **whether** a measurement can be trusted, **how** it compares with the astronaut's own usual range, and **what** deserves a look. Not a medical device: no diagnosis and no clinical advice.

This folder is the web interface. It works with the team's services in this repository:

| Service | Folder | Port | Used for |
|---|---|---|---|
| OrbitVitals server (FastAPI) | `../backend` | 8000 | measurements, data quality, personal baselines, evaluations |
| Assistant (agent) | `../ai_agent` | 8100 | explanations of stored results with NASA sources |
| Cognition battery | `../cognition-frontend` | bundled in (`#/cognition`) | the 10-test cognitive battery, used as it is |

## Run it

1. **Server** (from `backend/`):
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
   To load the team's reference data set: `python -m app.demo_seed seed --base-url http://127.0.0.1:8000/api/v1`.
2. **Assistant** (from `ai_agent/`, optional):
   ```bash
   python -m uvicorn orbit_agent.api:app --port 8100
   ```
   Without a local language model it answers with fixed, verified rules.
3. **Web interface** (from `frontend/`):
   ```bash
   npm ci
   npm run dev
   ```
   Open http://localhost:5173. `/api` and `/agent` are forwarded to ports 8000 and 8100.

On Windows, prefer `npm ci` to `npm install` (it keeps `package-lock.json` unchanged).

| Command | What it does |
|---|---|
| `npm run dev` | development server against the services above |
| `npm run build` | **delivery build**: cognition battery + type-check + production build in `dist/` |
| `npm run build:app` | the web interface only |
| `npm run preview` | serves `dist/` (with the same forwarding) |
| `npm test` | unit and contract tests (Vitest) |
| `npm run lint` | lint (oxlint) |
| `npm run dev:sample` | offline development with generated sample data (never for delivery) |

The cognition battery opens full screen at `#/cognition`. Its code is bundled into OrbitVitals unchanged (isolated, so its styles cannot affect the app), so it always works; when its own build with the face photographs is present (`npm run cognition`, part of `npm run build`), that build is shown instead.

Configuration is in `.env.example`: server and assistant addresses, which server crew members are Astronaut A/B/C (`VITE_BACKEND_CREW`), and optionally "now" and mission day 1. The mission plan (phases and activities such as spacewalks) is set by mission control in `src/mission.config.ts`; when empty, the header shows only the mission day.

## What it does

| Area | Address | Content |
|---|---|---|
| **Crew** | `#/crew` | Every astronaut at a glance (health, nutrition, tonight's sleeping pill, check-in) and who is ready to respond tonight. |
| **Astronaut · Today** | `#/crew/crew-a` | Nutrition first (water, energy, vitamins & minerals), the summary of what deserves a look, the daily review (check-in, measurement, sharing, sleep plan, exercise, cognition tests), health tiles and the trend of the selected one with data quality, personal baseline and trend. |
| **Astronaut · Health** | `…/health` | All 11 day-to-day indicators of the server's metric catalog. |
| **Astronaut · Nutrition** | `…/nutrition` | All 16 nutrients against NASA requirements (JSC-67378, same rules as `backend/app/domains/nutrition`), today or 7-day mean; log station foods, typed values or the crew's own foods; profile for the requirements. |
| **Astronaut · Sleep plan** | `…/sleep` | Phone-style month calendar of sleeping-pill nights: tap a day to change it, *+ Add* for one night or a repeating series; at least one person stays ready every night. |
| **Medical · Crew** | `#/medical` | To review (server evaluations needing attention, reports shared by the crew), tonight's readiness, a **status matrix** (astronauts × 12 indicators, latest reliable value coloured by distance from each astronaut's own usual range) and a **data-completeness map** (last 21 days). Click a cell to open that astronaut on that indicator. |
| **Medical · Astronaut** | `#/medical/crew/crew-b` | Status by area (server evaluations), shared items, a message to the astronaut, check-in trends; tabs **Trends** (12 indicators, daily chart against the usual range, daily distance in range units with a data-quality strip), **Evaluations** (timeline of evaluation windows by area, findings), **Nutrition** (7-day mean against NASA requirements), **Sleep**. |
| **Assistant** | `#/assistant` | Questions about one astronaut and one area, answered from stored results, with limits, suggested checks and NASA sources. |

The header switch moves between *Crew* and each astronaut; *Crew*, the logo and *Back* return to the astronaut and page used last.

**Data from the team's files:** *Settings → Import crew data (JSON + CSV)* reads a profile JSON and a measurements CSV, shows a preview, and sends the readings to the server. Formats: [`docs/FRONTEND_DATA_CONTRACT.md`](docs/FRONTEND_DATA_CONTRACT.md), examples in `docs/samples/`.

## Where data are kept

- **On the server:** measurements (including those typed in *Take a measurement* and imported files), the food log (as nutrition measurements), baselines and evaluations.
- **In the browser, for now:** check-ins, the sleeping-pill plan, messages between the crew and the medical team, shared reports, custom foods and the nutrition profile. The server has no endpoints for these yet; they are the next integration step.
- Physiological values are synthetic and tagged *Synthetic data* (crew health and medical header).
- Past mission days (day picker in the header) are read only: the interface refuses any change while one is shown.

Before real operational use: authentication and roles, durable server storage (the current API keeps data in memory), audit trail and secure storage for health data.

## Structure

```
docs/       DESIGN.md · UX_ANALYSIS.md · FRONTEND_DATA_CONTRACT.md · SUBMISSION.md · samples/
src/
  config.ts            addresses, crew mapping
  mission.config.ts    mission phases and activities (set by mission control)
  domain/              pure logic: quality, baselines, trends, nutrition, sleep plan, metric catalog
  data/                DataSource · backend/ (server adapter) · mock/ (sample data, development only) · import/
  views/crew/          Crew overview, Today, Health, Nutrition, Sleep plan
  views/medical/       Review, evaluations, sleep plan
  views/assistant/     Assistant and its client
  components/          shared interface components and charts
```

## Sources and tools to declare

- **UX research:** interviews with M. Cerri, D. Simeone, M. De Vittorio, P. Carlucci, L. Paciucci, F. Torchia, F. Ongaro (summary in `docs/UX_ANALYSIS.md`).
- **Requirements:** NASA JSC-67378 Rev 1 (nutrition), as implemented in the backend.
- **AI tools:** part of the interface code and documentation was produced with Claude (Anthropic) via Claude Code, under the team's review.
