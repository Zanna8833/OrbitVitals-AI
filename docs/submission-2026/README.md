# OrbitVitals AI submission drafts

Prepared on **2026-11-15** in `OrbitVitals-Codex`, branch
`feature/frontend-bridge`, against commit `036df20`. These are English drafts for
team review, not a submitted project or a statement of competition eligibility.

## Materials

| File                                                                 | Purpose                                                                                 |
| -------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| [Project copy](project-copy.md)                                      | Project description, executive summary, problem, solution and form-ready text           |
| [Science and validation](science-and-validation.md)                  | Methods, innovation, assumptions, evidence boundaries and limitations                   |
| [NASA provenance and references](nasa-provenance-and-references.md)  | NASA resource use, dataset distinction, statistical sources and acknowledgments         |
| [Architecture and implementation status](architecture-and-status.md) | Actual HTTP pipeline and implemented, tested, simulated and pending capabilities        |
| [Official rules and release checks](rules-and-release-checklist.md)  | Verified 2026 rules and administrative checks still requiring confirmation              |
| [Development AI and credits](ai-tools-and-credits.md)                | Confirmed team roles, development tools, model uncertainties and disclosure copy        |
| [Dependency inventory](software-inventory.json)                      | Pinned/locked direct dependencies and license-review boundaries                         |
| [29-second storyboard](video-storyboard.md)                          | Narration, shot descriptions, captions and recording gates                              |
| [Draft English captions](video-captions-draft.srt)                   | Text cues for the storyboard; synchronize with the actual recording before publication  |
| [Seven-slide alternative](seven-slide-script.md)                     | Exactly seven slides, including the title, with speaker notes and evidence requirements |
| [Demo 6 adapter mapping](demo6-adapter-mapping.md)                   | Crew/metric mappings, presentation conversions and unsupported states                   |
| [Demo 6 acceptance tests](demo6-acceptance.feature)                  | Executable-style acceptance specification for the future matching React source          |
| [Verification record](verification.md)                               | Commands, captured evidence, checks completed and checks not run                        |
| [Evidence](evidence/)                                                | Actual synthetic HTTP payloads and a separate capture manifest                          |

The storyboard and slide script are editable text drafts. No finished video,
PowerPoint, screenshot, generated image or live AI demonstration is supplied.

## Publication status

The scientific backend, scenario package, mission seeder and typed HTTP bridge
exist. The approved application is **Silvio's Demo 6**, represented by
`OrbitVitals_Demo (6).html`. Its matching final React source is being prepared.
The existing separate HTTP dashboard is **not** accepted as the final interface.
Frontend fidelity and final data integration remain release blockers.

The new material supersedes outdated implementation statements in the earlier
[demo planning package](../demo/README.md), which predates the completed seeder
and bridge. Those shared documents have not been edited. Earlier November scenario
dates and cadence-dependent quality values must not be mixed with the October
seeded HTTP evidence in this package.

## Evidence that can be presented

- Every astronaut observation is **SIMULATED**, with `source: "simulated"`.
- The isolated seeder run produced 498 measurements, 21 baselines and 13 evaluations.
- Crew B / Noor uses backend ID `sim-mission-v1-02`. The stored sleep replay moves
  from `insufficient_data` after two nights to `attention` after five and nine.
- The nine-night window contains seven recorded nights. Its median is 430 min;
  the selected personal reference median is 480 min. The reported slope is
  -15 min/day and fitted change is -120 min over eight elapsed days.
- In the captured default-cadence API configuration, Noor's record-quality checks
  pass while quality completeness is **null**. Missing nights and coverage appear
  in the sleep explanation. Seven of nine nights is not a Data Quality score.

See the [evidence record](verification.md) before quoting any number.

## Remaining decisions

The team has not independently confirmed its registered Local Event. The official
global requirements are used; local deadlines, pitch requirements and eligibility
remain pending. No event location, project page or public demo URL is invented.

Andrea coordinates final review. Marco reviews scientific claims and the separate
MedGemma contribution. Silvio supplies and accepts the matching Demo 6 React
implementation. Exact AI model versions across sessions and any generated media
still require team confirmation. Passing software tests is not clinical validation.

Only this dedicated directory is changed by the submission-preparation task.
No frontend, backend algorithm, shared contract, NASA pipeline or AI module is
modified. The initial drafts are approved for local preservation on
`feature/frontend-bridge`; see the [preservation review](verification.md#local-preservation-review).
That approval does not establish final publication readiness, scientific validation
or event eligibility. No push, merge or NASA submission is performed.
