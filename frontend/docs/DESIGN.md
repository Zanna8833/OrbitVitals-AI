# OrbitVitals — Interface design (redesign, 14 Nov 2026)

**Why this redesign.** Team feedback on the previous version: *“nice icons, but too much on screen and too many screens.”* The goal was a calm, Apple-like interface that keeps every capability backed by the interviews (`docs/UX_ANALYSIS.md`) while removing what competed for attention. Data layer, domain logic, API contract and tests are unchanged.

## Information architecture: from 7 screens to 2

| Before | After |
|---|---|
| Astronaut: *Overview*, *Take a measurement*, *During activity* tabs, five category sub-tabs, a status strip, a next-steps panel and four modal panels | **Crew · Today**: one scrolling page. Tasks open as **sheets** over it. |
| Flight Surgeon: dashboard, separate event page, crew sections, history table | **Medical · Review**: one split view. The list sits on the left, the selected item on the right, as in a mail app. |
| Header with 4 layers (disclaimer, navigation, clock, link, theme, auto-refresh, scenario bar, replay) | A single slim bar: brand · **Crew / Medical** · link status · **Demo** menu. Everything that exists only for the demo lives in that menu. |

Old links (`#/surgeon`, `#/events/EV-0142`, `#/crew/crew-a/health`) still work.

## One screen, no scrolling

On a laptop or desktop display (from 1024 × 620 up; checked at 1280 × 720, 1366 × 768, 1440 × 900 and 1920 × 1080), **every view fits the window with no page scroll**:

- each area is a full-height layout: crew in two columns; medical as list + detail with a side column;
- charts measure the space left and size themselves to fit (`hooks/useLayout.ts`);
- long content moves into sheets: *All indicators*, *Details*, *Compare signals*, check-in, measurement, share. The sheets fit the window too.

Phones and small windows (below 1024 × 620) keep a normal scrolling page: a full dashboard cannot fit on a phone screen.

**Alignment rules** (verified by measuring element positions in the browser):

- one horizontal margin (24 px) shared by the nav bar, the crew dashboard and the medical sidebar, so the logo, titles and cards line up;
- crew: both columns start and end on the same lines. The dashboard is as tall as the left column needs (never taller than the window) and the chart on the right adapts. On tall monitors it is centred, with no gaps inside the columns;
- medical: the sidebar title and the item title share the same baseline; the side column ends level with the figures, and the notes field takes the spare height;
- the stylesheet places the full-screen rules last, so they always take precedence.

**Density without clutter:** a tall screen shows the session plan in the *Now* card. When nothing needs attention, the summary card lists the five areas (heart, breathing, sleep, activity, body). While a scheduled activity is running, the link status sits inside the *Now* card instead of a separate banner. The sidebar uses short titles, and the message menu uses short labels; the full predefined text is shown below the menu.

## Crew area: Today, Health, Sleep plan (team feedback, 14 Nov evening)

Following team feedback (*"merge heart and the rest into one rectangle that opens its own page, so there is room for the rest"*):

- **Today** (home): on the left, the same three blocks as before (Now, summary, daily review). On the right, **one Health rectangle** (status + six key values) that opens the Health page, and the **Sleep plan** card (this week).
- **Health** (`#/crew/crew-a/health`): all 10 indicators, grouped by area, and the trend of the selected one.
- **Sleep plan** (`#/crew/crew-a/sleep`): a two-week crew calendar. Each crew member taps their own nights. Before a change that would leave nobody without a sleep aid, a sheet asks for confirmation (*Keep my night free* / *Plan anyway*). The Flight Surgeon sees the same plan under **Medical → Crew schedule → Sleep-aid plan**, with a badge for uncovered nights.
- Space is left for the modules still to come (cognition tests, nutrition and vitamins, exercise): each will be one card on Today that opens its own page, like Health.

The team's research note states that crews are sometimes all under sleep aids at once (a figure of about 16% was quoted). **The source has not been verified here**: cite it in the submission only after checking it, and do not show the figure in the interface.

## From prototype to platform (team feedback, 15 Nov evening)

- **No demo chrome.** The Demo menu, scenario switching, the "what is simulated" table and the offline demo file are gone. The interface talks to the OrbitVitals server by default; generated sample data remain only for offline development (`npm run dev:sample`). A gear menu holds *Settings*: server status, appearance, import of crew files, refresh.
- **Crew → astronaut.** Astronauts are named *Astronaut A/B/C*. The header switch keeps *Crew* (everyone) and one chip per astronaut. *Crew* in the bar, the logo and *Back* from the assistant resume the astronaut and page used last, instead of the crew list.
- **Assistant connected** to the team's agent (`ai_agent`, `/agent/v1/explanations`): pick the astronaut and the area, ask; the answer keeps the agent's structure (what the data show, how to read it, limits, checks for a person, NASA context with links) and says whether a language model or fixed rules wrote it.
- **Medical review** lists the server evaluations that need attention next to the reports shared by the crew.
- **Nutrition** has a profile (sex, age, height) for the requirements, and a barely-there green background so the slot reads as its own area.
- **Take a measurement** shows the instrument's steps and the fields to type its value; nothing pretends to read a device.
- **Mission plan** (phases, spacewalks…) comes from `src/mission.config.ts`; without it only the mission day is shown and no activity is invented.
- **Fixes:** daily-cadence freshness (a reading from this morning is not "Not updated"), an effect that broke the assistant on recent Chromium (scrollIntoView now returns a promise), names joined as "A, B and C", one y label on very short charts.

## Full platform pass (team feedback, 15 Nov afternoon)

- **Nutrition first.** A tinted slot at the top of Today, deliberately the most visible card: three rings (water, energy, vitamins & minerals on target), quick water buttons and *Log food*. NASA asks for 100% of each daily requirement, so the rings show what is still missing; anything above an upper limit (iron, sodium, phosphorus) turns orange. The Nutrition page lists all 16 nutrients. Targets use the backend rules (JSC-67378).
- **Crew and astronaut.** `#/crew` is the crew overview; a switch in every header moves between *Crew* and each astronaut on the same page type.
- **Every measurement.** *Take a measurement* lists all the catalog metrics measured on board, grouped (heart and circulation, breathing, body, sleep, exercise), each from the device (simulated) or typed by hand. *All indicators* shows all 11 day-to-day indicators.
- **Backend.** `VITE_DATA_SOURCE=http` reads and writes the team's FastAPI backend; tags say *Backend* / *Simulated records* / *Imported data*.
- **Sleep plan.** Explicit wording (*sleeping pill*) and a capsule icon, kept quiet; *Edit whole crew* lets the plan be changed for anyone. The ~16% figure from the team's research is still not shown: its source has not been verified.
- **Exercise and cognition** sit in *Daily review* as a compact pair.
- **Fixes:** chart labels moved to a strip above the plot (no text over the data), the tooltip floats above the page, focus rings and hover dots are no longer cut at the plot edges, y labels never stack, a clearer ringed-planet assistant icon. An automated check finds no overlapping or cut text on any page at 1280×720–1920×1080.

## Sleep plan made more useful + data import (team feedback, 15 Nov)

The calendar stays as it was; it now helps decide, not only record:

- **Next morning row:** the (simulated) mission activities of the following morning — spacewalk, cargo docking, medical checks — above each night. Your own are in blue. The plan is from `domain/missionPlan.ts` until mission control provides one.
- **Who stays ready:** the side card says who is without a sleep aid tonight, lists your planned nights (flagging those before one of your activities) and your next activity. Hovering the count at the bottom of a night shows the names.
- **Conflicts with a fix:** a night where everyone planned a sleep aid shows *Move mine to Thu 19*, the nearest night that keeps someone ready and has no activity of yours the next morning (`suggestNight`, tested). One tap moves it.
- **Ask before, with an alternative:** planning a night that would leave nobody ready, or a night before your own activity, opens a sheet with *Plan Thu 19 instead* / *Keep my night free* / *Plan anyway*. It says only *check the timing with your flight surgeon*: no advice on whether or what to take.
- The Flight Surgeon's *Nights without cover* list adds the activity of the next morning.

**Data import:** **Demo → Import crew data (JSON + CSV)** reads a profile JSON and a measurements CSV (wide or long layout, `,` or `;`, decimal commas), previews what was found and which rows were skipped, and replaces that crew member's simulated day-to-day data. Imported data are tagged *Imported data* instead of *Simulated*; baseline, quality and trend are computed on them exactly as on the demo data. Format and open questions: `docs/FRONTEND_DATA_CONTRACT.md`, samples in `docs/samples/`.

## What makes OrbitVitals different, made visible (team feedback, 15 Nov)

- **Three pillars** under every trend (`components/Pillars.tsx`, logic in `domain/pillars.ts`, tested):
  1. **Data quality** — reliable days out of total, today's quality, uncertain and missing days;
  2. **Personal baseline** — the usual range and the days it comes from;
  3. **Trend** — direction, size against the usual median, number of days, and whether it is *sustained* (≥ 3 days, the rule that flags it).

  Each pillar has an ⓘ that opens **How OrbitVitals reads your data** (`components/MethodSheet.tsx`): the method, its link to the interviews, and its limits. There are no invented references.
- **Charts:**
  - the tooltip adds the difference from the usual median, the day number within the current change (*Day 2 of 4 above usual*), and whether the reading is used for the baseline and trend;
  - the change zone is labelled on the chart.
- **Medical hierarchy:** **1 · Anomaly** (what and why) → **2 · Evidence** (chart, observed figures; *Context and provenance* opens as a sheet) → **3 · Next steps**. The steps are a review workflow derived from the data, never clinical advice; where relevant a button pre-selects the matching message. Then come *Assessment* and the *Message to crew*.
- **Mission context:** mission elapsed time (`T+14d 10:40`) next to UTC in the nav bar, in addition to the mission-day timeline.
- **Real vs simulated:**
  - a dashed **Simulated** tag on everything simulated, in particular communications: *Simulated delivery* on the crew share sheet and the medical message, *Simulated message* on what the crew receives;
  - the footer link **What is real, what is simulated?** opens a table: Working / Simulated / Not connected.

## Today layout restored (team preference, 14 Nov late evening)

The team preferred the Today layout with **Your health** tiles and the trend chart on the home screen, so it is back:

- right column: six tiles (any indicator needing attention always gets one) and the trend of the selected tile; *All indicators (10)* opens the Health page;
- the **Sleep plan** is now the fourth row of *Daily review*. It shows tonight's status, and a badge and warning when a night in the next week would leave nobody without a sleep aid. It opens the two-week calendar;
- the summary card is white again; only the small *Worth a look* label marks it;
- everything else from the refinements below is kept.

## Refinements (team review, 14 Nov evening)

- **Emphasis:** the summary card is tinted and labelled (*Worth a look* / *To check*) when something deserves attention. Secondary text (daily review subtitles, phase captions) recedes to the tertiary grey. In the Health rectangle only the indicators that changed keep their colour.
- **Charts:**
  - the personal usual range has hairline edges and a direct *usual* label;
  - the baseline days are a quiet bracket at the top instead of a grey block;
  - days without a reading are hatched columns, never interpolated;
  - a custom tooltip (day, value, quality, position against the usual range) replaces the browser tooltip, with keyboard navigation (← → Home End Esc).
- **Medical:** three registers are told apart. **Explanation** (*Why it is here*) sits in a grey box with an info icon. **Observed** facts carry a label: computed, no interpretation. **Assessment** (status + notes) is separate from the **Action** (message to the crew), which has a tinted block. Short labels prevent truncation in the sidebar and in the message menu.
- **Mission identity:** a mission-day indicator with a phase timeline (*Launch & docking → Adaptation → Science operations → Return preparation*) sits in the Today header, marked *sim*. The plan is simulated (`domain/missionPlan.ts`) until mission control provides one.
- **Micro-interactions:**
  - pages fade in on arrival;
  - loading shows shaped placeholders instead of text;
  - buttons and toggles give a press response;
  - every save (check-in, reading, sleep plan, note, status, message) confirms with a short toast;
  - everything respects *reduced motion*.
- **Assistant slot:** a small *Assistant* bubble on the right of the footer, deliberately out of the way, opens `#/assistant`. That page is a placeholder for the team's language model: nothing is connected, the composer is disabled, and the page states what the assistant will and will not do (no diagnosis, cites its data). The integration point is `views/assistant/AssistantPage.tsx`.

## Crew · Today (order = priority)

Left column, top to bottom; right column: six health tiles and the trend of the selected tile.

1. **Now**: shown only while a scheduled activity is in progress. It shows the phase, time left, whether data is reaching the ground and a sensor problem if there is one. An instruction appears only when the medical team asked for one. Otherwise: *“Nothing to do — carry on.”* (Carlucci/Paciucci, Torchia: minimal load during the activity.)
2. **One summary card**: the single thing that deserves attention (a sustained change from the personal pattern, or a reading to repeat), with at most two actions. When nothing needs attention, it says so. (Cerri: personal context; no diagnosis.)
3. **Daily review**: three rows (check-in, measurement, share). Each one opens a sheet.
4. **Your health** (right): six tiles, always including any indicator that needs attention. Selecting a tile shows its trend against the usual range in the large card below. *Details* adds the source and explanation; *All indicators* lists all ten.

## Medical · Review

- **Sidebar**: items *To review* (or *All*) and the crew with data freshness.
- **Event** includes:
  - why it is here (the demo rule);
  - one main chart: event ±5 min or the whole session; *Compare signals* opens all four signals with a shared cursor;
  - four **observed figures** computed from the samples (no interpretation);
  - context and provenance behind a disclosure;
  - **Your review** card: status, notes and a predefined message to the crew.
- **Crew member**: latest values with quality, the current session, and only the day-to-day indicators that changed.

## Visual system (`frontend/src/index.css`)

- **Type:** system font (SF Pro on Apple devices, Segoe UI on Windows), large titles at 34 px, 15 px body text, no display fonts.
- **Surfaces:** grouped background `#f5f5f7` / `#000`, white or `#1c1c1e` cards, hairline separators, 16 px radius. No gradients, no glass effect except the functional translucent nav bar, no decorative shadows.
- **Colour:**
  - One tint for actions (`#0071e3` / `#2997ff`).
  - Category colours (heart, respiration, rest, activity, body) only on labels and trends.
  - Orange only for “attention”. Red is never used, so nothing reads as an alarm.
  - Every state also has a **shape and a label**.
- **Components:** `components/ui.tsx` provides:
  - `Sheet`, built on native `<dialog>`, so the focus trap, Esc and the inert background come for free; it becomes a bottom sheet on phones;
  - `Segmented`;
  - grouped `List`/`Row`;
  - `Symbol`.

  The charts (`TimeSeriesChart`, `DailyTrendChart`) are the same components as before, restyled.
- **Appearance:** Auto / Light / Dark from the Demo menu.
- **Responsive:** checked at 1440, 1280 and 390 px. The medical split view turns into list → detail on narrow screens.

## Verified

- `tsc`, build, and 101 unit/contract tests pass.
- End-to-end browser run, with no console errors:
  - indicator sheet and Esc to close;
  - check-in; measurement with a paired blood-pressure capture; share;
  - the shared report appears in Medical; status change, note and message;
  - the message appears in the crew's Now card;
  - offline queue, then delivery on reconnection;
  - the standalone demo opened from `file://`.
- Not tested with real users. That remains the next step (see `UX_ANALYSIS.md` §7).
