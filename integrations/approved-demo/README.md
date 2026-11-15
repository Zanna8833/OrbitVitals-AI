# Approved frontend scenario on FastAPI

All values here are **SIMULATED**, not astronaut records.

1. `node integrations/approved-demo/export_observations.mjs` runs the unchanged frontend
   generators (`frontend/src/data/mock`) at the approved clock (2026-11-14 10:40 UTC,
   mission day 15, day 1 = 2026-10-31) and writes
   `backend/app/demo_seed/approved_observations.json`. Each daily value becomes one backend
   measurement with the frontend's own `importDaily`/`addIntake` mapping. Days the
   generators mark missing are not stored.
2. `python -m app.demo_seed.approved --base-url <api>` ingests them into a **fresh** API.
   The backend then computes data quality, personal baselines over mission days 1-7 (the
   approved interface's window and its five-reading minimum) and a sleep evaluation for
   days 8-15 with the official seed's documented SIMULATED sleep policy.
3. Start the dashboard with `VITE_AS_OF=2026-11-14T10:40:00Z` and
   `VITE_MISSION_START=2026-10-31`.
4. `node integrations/approved-demo/compare_sources.mjs <api>` compares Demo mode with
   Demo off through the frontend's own data adapters.

## Verified on 2026-11-15

- Plotted daily values, Astronauts A/B/C, 12 indicators x 15 days (540 points, including
  mission days 1, 5, 6, 8 and 15): **0 differences**. Nutrition per day (entries, kcal,
  mL) on days 1, 5, 6, 8 and 15: **0 differences**.
- Screens, Demo on vs Demo off (1440x900): Crew A 0.7 % of pixels differ, Crew B 0.8 %,
  Crew C 44.7 % (the demo's "device not sending data" scenario for Astronaut C exists only
  in Demo mode), Medical 11.4 % (the demo's three rule-generated review events). No 5xx.
- The 18 reference screens of Demo mode stay identical (the frontend is unchanged).
- The Assistant (Gemma 3 4B) reads the selected astronaut's records from this backend:
  Crew A's sleep answer cites the backend evaluation of days 8-15.

## Remaining differences (not forced)

| Item | Demo mode (interface) | Demo off (backend) | Why |
| --- | --- | --- | --- |
| Quality flags | some days "uncertain" (illustrative) | "good": A 13, B 6, C 18 days | The Data Quality engine assesses the records; it does not copy the interface's labels |
| Usual ranges | good-quality days only | engine statistics over days 1-7 | 12 of 36 ranges differ by 1-6 units, e.g. Crew A HRV 36-54 vs 30-60; heart rate and A/B sleep ranges match |
| Sleep status | A: "lower than usual for 4 days" | A: nominal; B, C: attention | Backend sleep engine with the seed's policy, not the interface rule |
| Vital-sign status | interface trend rule | none | The backend has no vital-sign evaluation |
| Sleep range label | days 1-7 | days 0-6 | `BackendDataSource.baselineFrom` counts a noon-started sleep window from its start day; its unit test fixes that convention, so it is left to the frontend owner |
| Review events, device-offline scenario, sleep-aid plan, "15 of 180", nutrition targets of the profile | approved demo scenario | adapter's local `nominal` state | Workflow state with no backend contract, kept as designed by the frontend |
| Food-log entry names | food names | "Logged intake" | Backend measurements carry no label |
