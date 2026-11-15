# 29-second video storyboard

**Draft, not a finished recording.** The
[official 2026 submission guide](https://www.spaceappschallenge.org/resources/project-submission-guide/)
confirms a maximum of 30 seconds. This plan reserves one second of margin, including
any title and ending. Record and measure the exported file; planned timing is not
proof of actual duration.

Use the unchanged approved Demo 6 design only after its matching React integration
passes acceptance. No screenshot, result, control, interaction or AI conversation
should be fabricated to complete a shot. The machine-readable timing and narration
are in [video-storyboard.json](video-storyboard.json).

| Time      | Shot                                                                            | Narration                                                                              |
| --------- | ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| 0:00–0:03 | Demo 6 Today, Crew B / Noor; preserve the dashboard hierarchy                   | OrbitVitals helps astronauts review changing health data.                              |
| 0:03–0:07 | Select the original sleep card; expose the actual quality assessment            | Meet Noor: simulated records, checked for data quality.                                |
| 0:07–0:11 | Show the selected personal reference: median 480 min, 14 simulated observations | Her personal median reference is eight hours.                                          |
| 0:11–0:17 | Replay the actual 2- and 5-night stored results                                 | Two nights are insufficient. Five prompt review.                                       |
| 0:17–0:24 | Nine-night chart: seven points and two gaps; real explanation                   | After nine, seven recorded nights show a continuing reduction. Two nights are missing. |
| 0:24–0:29 | Human-review caption over actual evidence; no unsupported action                | Review the record with a flight surgeon. No diagnosis is made.                         |

Keep **SIMULATED DATA · Research prototype · Not a medical device** legible for the
whole video. Display captions in English. The reference is personal, not a sleep
target. Eight hours is a display conversion of the actual 480 min median.

## On-screen evidence

- After two nights: `insufficient_data`; 2/2 recorded nights; window median 482.5 min.
- After five: `attention`; 4/5 recorded nights; window median 460 min.
- After nine: `attention`; 7/9 recorded nights; window median 430 min; selected
  reference 480 min. The engine explanation reports slope -15 min/day and fitted
  change -120 min over eight elapsed days.
- Quality: the captured configuration reports `acceptable`, with completeness
  unassessed. Show missing nights separately. Never add a 78% Data Quality or
  confidence badge to this capture.
- Attribution: a small final credit or video description links the
  [NASA sleep-risk resource](https://www.nasa.gov/reference/risk-from-inadequate-sleep-and-irregular-schedules/)
  and the [source ledger](nasa-provenance-and-references.md). NASA supplies context,
  not the synthetic observations or policy values.

The last nightly duration is 370 min, while the nine-night median is 430 min.
Do not interchange them. Do not label the 50 min median/reference difference as
the -120 min fitted change. No medication, treatment, urgency or impairment claim
belongs in the narration.

## Recording gates and fallback

1. Obtain Silvio's matching source and a successful visual/interaction comparison.
2. Verify the actual controls for checkpoint selection and evidence access. Their
   placement in the approved UI is pending; do not invent a replay widget in a mockup.
3. Seed an isolated API and verify result IDs against the captured payloads.
4. Rehearse narration; fit it to the real captures and preserve readable labels.
5. Check export duration, English captions, source credits and the final AI/media
   disclosure. No generated voice or imagery is assumed by this draft.
6. Test the real public demo link without authentication before submission.

If the interface cannot be captured honestly in time, use the
[seven-slide alternative](seven-slide-script.md) built from the actual evidence.
Label any API/evidence view as an engine demonstration, not an integrated Demo 6
screen. The storyboard does not imply that the interface is already ready to film.
