# Seven-slide alternative presentation

**Text draft: exactly seven slides, including the title.** No finished deck or
dashboard screenshot is claimed. The
[official judging guide](https://www.spaceappschallenge.org/resources/judging-awards-guide/)
confirms the seven-slide maximum. Do not add a cover, appendix or credits slide
beyond these seven. Local live-pitch requirements remain unverified.

Use real evidence extracts, editable tables and a chart of the captured CSV.
Approved UI captures may be added only after Demo 6 acceptance. No generated
screenshot, fabricated control or AI conversation is required. Keep a legible
simulation/prototype disclosure on every slide; place full references in the
public project page and speaker notes.

## Slide 1 — OrbitVitals AI

**On screen**

Explainable physiological review for space crews

Data quality · Personal reference · Change over time

SIMULATED DATA · Research prototype · Not a medical device

**Speaker notes**

OrbitVitals keeps the quality of an observation, the maturity of a personal
reference and the result of a statistical screen separate. It supports human
inspection and review. The demonstrated case uses synthetic records and real
scientific algorithms.

**Asset/source**: Project title and team-owned text. If a UI image is used, use
an actual accepted Demo 6 capture. No NASA insignia or stock astronaut image is needed.

## Slide 2 — Trust before interpretation

**On screen**

- Quality checks describe whether observations can be used.
- Personal baselines describe the individual's reference history.
- Trend screens explain what met an explicit policy.

**Speaker notes**

A suspect reading does not automatically indicate a health emergency. The Data
Quality Engine runs before interpretation. The baseline and sleep screen then
use eligible data and retain reasons for exclusions. These are transparent
statistical methods, not a runtime language-model diagnosis.

**Asset/source**: A simple, editable three-step diagram labelled with the actual
engine names. Source: [scientific methods](science-and-validation.md) and existing
backend implementations. Do not present a conceptual diagram as an application screen.

## Slide 3 — Noor's personal reference

**On screen**

Crew B / Noor · `sim-mission-v1-02`

| Reference              | Actual result                                      |
| ---------------------- | -------------------------------------------------- |
| Metric and phase       | Sleep duration · in flight                         |
| Reference observations | 14 synthetic records                               |
| Personal median        | 480 min / 8 h                                      |
| Status                 | Established under a synthetic demonstration policy |

Personal reference, not a sleep target

**Speaker notes**

The reference window ends at the start of the evaluated window and belongs to the
same crew member and mission phase. Establishment criteria are chosen for the
demonstration; the status is not evidence of healthy sleep or clinical validity.

**Asset/source**: Actual selected reference in
[noor-sleep-baselines.json](evidence/noor-sleep-baselines.json), with its ID,
algorithm/version and window available in notes. Reference median 480 min, not
a population threshold or NASA recommendation.

## Slide 4 — Evidence accumulates

**On screen**

| Window   | Recorded nights | Window median | Actual finding   |
| -------- | --------------- | ------------- | ---------------- |
| 2 nights | 2/2             | 482.5 min     | Not enough data  |
| 5 nights | 4/5             | 460 min       | Review suggested |
| 9 nights | 7/9             | 430 min       | Review suggested |

Nine-night explanation: -15 min/day · -120 min fitted change

**Speaker notes**

The engine can describe a slope after two nights, but the sufficiency policy
still refuses a conclusion. As observations accumulate, the configured trend
criterion is met. The nine-night median is 50 min below the selected reference;
the trend prompts attention even though the absolute-deviation criterion is not met.

**Asset/source**: Actual evaluations in
[noor-sleep-evaluations.json](evidence/noor-sleep-evaluations.json). A native chart
may use [the nine-night CSV](evidence/noor-nine-night-observations.csv). Keep the
two gaps; do not join or replace them with zeros. The most recent night is 370 min,
which is different from the 430 min window median.

## Slide 5 — Quality and uncertainty remain visible

**On screen**

- Seven night records pass the configured checks.
- Two night buckets are missing: October 14 and October 18.
- Quality completeness is unassessed in this server configuration.
- Missing information remains missing.

**Speaker notes**

Noor's stored quality is `acceptable` under the checks that were configured.
This is not proof of sensor accuracy. No expected sleep sampling interval was
configured, so the quality completeness field is null. The sleep module separately
states seven of nine nights and the missing dates. Do not call that a 78% quality,
confidence or accuracy score.

**Asset/source**: The actual quality notes and sleep explanation in the captured
evaluation, with per-metric quality distinct from the evaluation rollup. No warning
color or icon is used to imply a medical emergency.

## Slide 6 — NASA context and traceable explanation

**On screen**

NASA HRP identifies inadequate sleep and irregular schedules as a spaceflight risk.

OrbitVitals records the algorithm, policy, window, reference and explanation.

NASA resources provide context; demonstrated observations are simulated.

**Speaker notes**

NASA resources motivate monitoring sleep and activity. They do not supply this
demo's observations or thresholds, and NASA has not validated the prototype.
The explanation is produced by the existing statistical engine. An integrated
NASA retrieval assistant or MedGemma service is not part of the demonstrated run.

**Asset/source**: [NASA sleep-risk resource](https://www.nasa.gov/reference/risk-from-inadequate-sleep-and-irregular-schedules/)
and [provenance ledger](nasa-provenance-and-references.md). Use a short actual
engine excerpt with the stored result ID; do not invent an AI-generated explanation.

## Slide 7 — Human review and next steps

**On screen**

Review the observations and missing nights with a flight surgeon.

Demonstrated: deterministic engines, canonical contracts and real HTTP replay

Pending: accepted Demo 6 integration, real-data evaluation and separate AI work

Andrea · Marco · Silvio

**Speaker notes**

The next step is human review, not an automated diagnosis or treatment. HTTP
sharing, messaging and clinical recommendations are unavailable; this statement
does not imply a report has been sent. Marco's MedGemma 1.5 work remains separate
pending confirmation. Development assistance from Codex, ChatGPT, Claude Code and
locally hosted Qwen 3.5 4B is disclosed in the project materials. Exact versions
and media provenance remain part of final team review.

**Asset/source**: [Contributor and AI disclosure](ai-tools-and-credits.md),
[verification record](verification.md), [limitations](science-and-validation.md).
Use a short public source/disclosure link on this slide once the real URL exists;
do not invent a QR code destination or claim that an unpublished branch is public.

## Assembly acceptance

Use exactly these seven slides. Check large text, readable units, English language,
complete references, simulation notices and accessible public links. If time is
limited, a faithful table/diagram deck is preferable to a fabricated dashboard
capture. Human review of final content, actual rendered slides and any media rights
is required before publication. This text draft is not proof of slide rendering.
