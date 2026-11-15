# Example responses

Real responses of the integrated assistant (schema 0.2.0), saved as they were returned.
They can be used as fixtures while building the dashboard.

- Crew data: **SIMULATED**, read from a local backend seeded with the existing Mission
  Demo Seeder (`sim-mission-v1-01` is "Vega", `sim-mission-v1-02` is "Noor" / Crew B,
  `sim-mission-v1-03` is "Chen").
- Evidence: summaries written by the OrbitVitals team of paragraphs on public NASA
  pages and in open-access peer-reviewed articles, with their source URLs or DOIs;
  general context only, not the sources' text (see
  [NOTICE.md](../orbit_agent/evidence/corpus/NOTICE.md)).
- NASA dataset evidence: read from the backend's NASA Dataset Evidence Adapter (merged
  into this branch); research context about bed-rest volunteers, not crew data.
- Specialist background: sections of `rag/knowledge_base` admitted by the review in
  `orbit_agent/specialist_evidence/admission.json`, listed by document and section only.
- Models: `qwen3.5:4b` writes; `medgemma1.5:4b` reviews when routing asks for it. Both
  through Ollama on the development machine, recorded on 2026-11-15.

| File | Request | What it shows |
| --- | --- | --- |
| `noor_sleep.generative.json` | Noor, domain `sleep`, "why is it flagged" | Full Qwen draft; MedGemma consulted (no `rag/` section relevant enough) |
| `noor_activity_specialist_rag.generative.json` | Noor, `physical_activity`, "a concern for muscle and bone loss?" | MedGemma consulted with two admitted `rag/` sections (`generation.specialist.evidence`) |
| `noor_sleep.brief.json` | Noor, "what was the latest sleep duration?" | Brief Qwen draft; MedGemma not consulted (`factual_question`) |
| `noor_sleep.deterministic.json` | Same as the first, `mode: "deterministic"` | Rule-based only; no model |
| `noor_greeting.generative.json` | Noor, "Hello!" | Conversational reply: headline only, no report, no review banner |
| `noor_greeting.it.generative.json` | Noor, a greeting in Italian | The same, answered in Italian (`generation.reply_language: "it"`) |
| `noor_general_bones.generative.json` | Noor, "how does microgravity affect bones in general?" | General answer from bone evidence, not from Noor's flagged sleep |
| `crew_a_sleep.it.generative.json` | Crew A, how long Crew A slept, in Italian | Brief answer in Italian, values from the backend |
| `noor_sleep_worse.it.generative.json` | Noor, `sleep`, why sleep got worse, in Italian | Full Italian answer reviewed by MedGemma; fixed rule-based sentences stay English |
| `crew_a_follow_up.generative.json` | Crew A, "And compared to yesterday?" with two earlier turns in `conversation` | Follow-up understood from the history (`generation.context_turns: 2`) |
| `chen.generative.json` | Chen, all domains, "can we trust the readings?" | Data-quality explanation; MedGemma not consulted |
| `chen.deterministic.json` | Same request, `mode: "deterministic"` | Rule-based only |
| `vega_nasa_dataset.generative.json` | Vega, "NASA research data on heart rate in tilt tests?" | `dataset_evidence` with MR001G context and unresolved units |

A model-written sentence that passed the verifier can still be imprecise; see "Limits"
in the [agent README](../README.md). `verification.rejected_statements` lists what the
verifier removed from each draft, and `generation.specialist.findings` what the reviewer
changed. These files are illustrations of software behaviour, not assessments of a person.
