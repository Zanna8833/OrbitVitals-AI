# Test fixtures

`backend/` holds unmodified JSON responses of the OrbitVitals backend, recorded on
2026-11-14 from the code at commit `e08becd` after running the existing Mission Demo
Seeder (`python -m app.demo_seed seed`) against a fresh in-memory instance.

- Every measurement in these files is **SIMULATED** (`source: "simulated"`). They are
  not recordings of a person.
- `sim-mission-v1-02` is the simulated crew member "Noor" (declining sleep).
- `sim-mission-v1-03` is the simulated crew member "Chen" (sensor failures, missing data).
- Statuses, statistics and quality assessments were computed by the backend. Nothing was
  edited by hand, so the tests check the agent against real engine output.

To refresh them, seed a local backend and save the bodies of `GET /metrics` and of
`GET /crew-members/{id}/{evaluations,baselines,measurements}` under the same names.
