# Example responses

Real responses of the agent, saved as they were returned. They can be used as fixtures
while building the dashboard.

- Crew data: **SIMULATED**, read from a local backend seeded with the existing Mission
  Demo Seeder (`sim-mission-v1-02` is "Noor", `sim-mission-v1-03` is "Chen").
- Evidence: summaries written by the OrbitVitals team of paragraphs on public NASA
  pages, with their source URLs; general context only, not NASA text (see
  [NOTICE.md](../orbit_agent/evidence/corpus/NOTICE.md)).
- Model: `qwen3.5:4b` through Ollama on the development machine, recorded on 2026-11-15.

| File | Request | Mode |
| --- | --- | --- |
| `noor_sleep.generative.json` | Noor, domain `sleep`, with a question | Model draft, verified |
| `noor_sleep.deterministic.json` | Same request with `mode: "deterministic"` | Rule-based only |
| `chen.generative.json` | Chen, all domains, with a question | Model draft, verified |
| `chen.deterministic.json` | Same request with `mode: "deterministic"` | Rule-based only |

A model-written sentence that passed the verifier can still be imprecise; see "Limits"
in the [agent README](../README.md). `verification.rejected_statements` lists what the
verifier removed from each draft. These files are illustrations of software behaviour,
not assessments of a person.
