# Primary demonstration flow

One story, two scenes, told from the astronaut's seat. Every number below was produced by the
existing engines on 2026-11-14 at commit `667f512`, through the scenario replay command and
through the real HTTP API. Nothing here is a mock-up output.

All data is **simulated**. OrbitVitals AI is a research prototype, not a medical device.

## 1. The idea in one line

> Two readings look wrong. One is a broken measurement. The other is a real change that no
> single reading reveals. OrbitVitals AI tells them apart, explains why, and says what to do
> next.

Why this pair: it shows in under a minute the one thing a number-to-colour dashboard cannot do.
In Scene A the most dramatic value on the screen is the one to ignore. In Scene B every value
looks ordinary and the finding is in the sequence.

## 2. The reasoning chain

Both scenes follow the same eight steps. The "Verified by" column says how each step was
confirmed today.

| Step | Question for the astronaut | Engine | Verified by |
| --- | --- | --- | --- |
| 1 | Did my measurements arrive? | `POST /measurements` | HTTP run |
| 2 | Can each one be trusted? | Data Quality Engine, per record and per window | Replay and HTTP run |
| 3 | Do I have a personal reference? | Personal Baseline Engine | Replay (`personalized_baseline`); API tests |
| 4 | Which mission phase and which history apply? | `mission_phase` on the command; window of nights | Replay and HTTP run |
| 5 | Did something meaningfully change? | Sleep trend screen | Replay and HTTP run |
| 6 | Why does the system say so? | `summary` and per-metric `explanation` | Replay and HTTP run |
| 7 | Is this a measurement problem or a change in me? | Separate `data_quality` and `status` fields | Replay and HTTP run |
| 8 | What should I do next? | **Not implemented.** Proposed interface behaviour | See section 6 |

Step 8 is the only step with no backend support. It is the most important gap against the
challenge wording ("act on the status of their health").

## 3. Scene A: a measurement that cannot be right

Scenario `sensor_quality_failure`. Seven nights of sleep summaries for one simulated crew
member, in flight. The fixture is constant (480 min, 92% efficiency) except for three injected
faults.

| Night (UTC) | Sleep duration | Sleep efficiency | What happened |
| --- | --- | --- | --- |
| Nov 1 and 2 | 480 min | 92% | |
| Nov 3 | 480 min | **125%** | Impossible percentage |
| Nov 4 | 480 min, **recorded twice** | 92% | Redundant copy with a different identifier |
| Nov 5 | 480 min | 92% | |
| Nov 6 | **-30 min** | 92% | Impossible duration |
| Nov 7 | 480 min | 92% | |

### What the system actually returns

| Step | Actual output |
| --- | --- |
| 1. Arrival | 15 records ingested |
| 2. Trust | 12 `acceptable`, 3 `unusable`. Notes, verbatim: "Value -30 min is impossible for sleep_duration: by definition the metric lies at or above 0 min." "Value 125 % is impossible for sleep_efficiency: by definition the metric lies between 0 and 100 %." "Redundant copy of measurement '...' (same crew member, metric, time, source, device and value); only one copy is used." |
| 2. Trust, window | Both metrics `degraded`; flags `signal_artifact` and `duplicate` for duration, `signal_artifact` for efficiency; completeness 1.0; score 0.857 |
| 3. Reference | None supplied. The explanation states: "No personal baseline supplied; no personal-reference comparison made." |
| 4. History | 6 of 7 nights usable per metric; the faulty night is listed as missing (Nov 6 for duration, Nov 3 for efficiency) |
| 5. Change | Slope 0 min/day, fitted change 0 min. "No configured trend pattern detected." |
| 6. Explanation | Lists the included nights, the excluded records and the gates applied |
| 7. Separation | Evaluation `status: nominal`; evaluation `data_quality.status: degraded`. No `alert`, no `attention` |

### What to say

"On night six the tracker reported minus thirty minutes of sleep. A simple dashboard would plot
a crash. OrbitVitals marks that record unusable, says why, and keeps it out of the analysis. The
six trustworthy nights show no trend. Notice the wording: 'no configured signal', not 'healthy'.
And the data-quality badge stays amber, because one night is still unaccounted for."

### What the astronaut can do

A measurement problem leads to a measurement action: check the device, and record the night
again if the information exists. No health conclusion was drawn. (Proposed interface behaviour.)

### Honest scope

The quality engine caught these faults because each one is provable from the data. It would not
catch a plausible but wrong value, such as a tracker that under-reports by an hour. Do not
describe Scene A as "sensor failure detection" without that qualification.

## 4. Scene B: a change no single reading shows

Scenario `progressive_sleep_restriction`. Nine nights, in flight. Sleep duration falls by 15
minutes each night, from 490 to 370 min. Efficiency stays at 92%. Two nights (Nov 3 and Nov 7)
were never recorded. No individual value is impossible or even striking.

| Night (UTC) | Nov 1 | Nov 2 | Nov 3 | Nov 4 | Nov 5 | Nov 6 | Nov 7 | Nov 8 | Nov 9 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Duration (min) | 490 | 475 | missing | 445 | 430 | 415 | missing | 385 | 370 |

### The same question asked at three moments

This is the centrepiece. The system's answer changes as evidence accumulates, and it declines to
answer when there is too little.

| | After 2 nights | After 5 nights | After 9 nights |
| --- | --- | --- | --- |
| Checkpoint (UTC) | Nov 3, 12:00 | Nov 6, 12:00 | Nov 10, 12:00 |
| Nights used | 2 of 2 | 4 of 5 | 7 of 9 |
| Data quality (duration) | `acceptable` | `degraded`, `missing_data` | `degraded`, `missing_data`, completeness 0.78 |
| Slope | -15 min/day | -15 min/day | -15 min/day |
| Fitted change | -15 min | -60 min | -120 min over 8 days |
| Median duration | 482.5 min | 460 min | 430 min |
| Sleep duration status | **`insufficient_data`** | **`attention`** | **`attention`** |
| Reason given | "Insufficient trend data: too_few_nights, time_span_below_minimum." | "Configured statistical pattern detected: progressive_duration_reduction." | Same pattern; "missing nights=2026-11-03, 2026-11-07" |
| Sleep efficiency status | `insufficient_data` | `nominal` | `nominal` |

At the first checkpoint the slope is already -15 min/day. The system still answers "not enough
data", because two nights cannot support a conclusion. That refusal is a feature worth showing.

### What the system actually returns at the last checkpoint

| Step | Actual output |
| --- | --- |
| 1. Arrival | 14 records ingested (7 nights, two metrics) |
| 2. Trust | All 14 `acceptable` individually. Per-metric window quality `degraded` with `missing_data`: "7 distinct observation times for 9 expected (one every 1 day)" |
| 3. Reference | None supplied; stated in the explanation |
| 4. History | Mission phase `in_flight`; window Nov 1 12:00 to Nov 10 12:00 UTC; missing nights named, not filled in |
| 5. Change | `sleep_duration`: `attention`, median 430 min, Theil-Sen slope -15 min/day, fitted change -120 min, all adjacent recorded nights decreasing |
| 6. Explanation | Verbatim excerpt: "Included 7/9 complete night buckets; coverage=0.777778; missing nights=2026-11-03, 2026-11-07 ... Theil-Sen slope=-15 min/day; fitted change=-120 min ... Configured statistical pattern detected: progressive_duration_reduction." |
| 7. Separation | Evaluation `status: attention`; `data_quality.status: degraded`. The finding stands, and its uncertainty is shown beside it |

### What to say

"Now a different crew member. Nothing here looks wrong. But across nine nights, recorded sleep
has fallen by about fifteen minutes a night, two hours in total. After two nights the system
would not judge. After five it asked for review. After nine the pattern is clearer, and it still
tells me two nights are missing, so I know how much to trust it. This is a statistical screen
with settings chosen for this demonstration. It is asking a person to look, not making a
diagnosis."

### What the astronaut can do

A possible physiological change leads to a human review: fill in the missing nights if the
information exists, read what NASA says about this risk, and share the finding with the flight
surgeon. (Proposed interface behaviour; see section 6.)

## 5. The contrast

| | Scene A | Scene B |
| --- | --- | --- |
| What looks alarming | One absurd value | Nothing |
| Individual records | 3 of 15 unusable | All acceptable |
| Evaluation status | `nominal` | `attention` |
| Data quality | `degraded` (faulty records) | `degraded` (missing nights) |
| Kind of problem | Measurement | Possible change in the person |
| Sensible next step | Check the device, re-record | Human review |

Both scenes end with the same amber data-quality badge and opposite conclusions. That is the
proof that the two questions are answered separately.

## 6. Step 8: follow-up, as a proposal

Nothing in this section exists in the backend. It is specified in
[frontend-demo-mapping.md](frontend-demo-mapping.md#6-follow-up-actions). The minimum that makes
the demonstration answer the challenge:

| Finding | What the astronaut sees | Meaning | Trust | Remaining uncertainty | More measurements? | Safe follow-up | Human review |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Scene A | "3 records could not be used" | The device or the transfer produced invalid values | The 12 other records passed the available checks | Night 6 is unknown | Yes: re-record night 6 if possible | Check the device and its connection | Not needed for health; report the fault if it repeats |
| Scene B | "Your recorded sleep has been getting shorter" | A sustained downward pattern met the demonstration settings | 7 of 9 nights; all records passed checks | Two nights missing; no personal reference; no cause identified | Yes: add the two missing nights | Read NASA's description of the sleep risk; note schedule or environment changes | Suggested: share the summary with the flight surgeon |

The system never chooses a treatment, a medication or an urgency level.

## 7. Optional secondary views

Use these only if time allows. Each is an existing replay scenario.

- **Personal reference by mission phase** (`personalized_baseline`). Heart rate: pre-flight
  reference `established` from 14 values, median 58 bpm; launch `insufficient_data` (one value);
  in-flight `established` from 12 values, median 64 bpm, quality `degraded` because two corrupt
  readings were excluded; post-flight not yet available (`null`). Remove the establishment policy
  and both references fall back to `provisional`. Say "one reference per phase". Do not say the
  rise is an expected adaptation; the values are authored (see evidence item E4).
- **Exercise adherence** (`exercise_adherence_change`). Fourteen days against a simulated plan of
  40 min a day: two runs of decreasing daily totals (60 to 40 min, then 35 to 20 min), five
  missed daily targets, a planned rest day that is not counted as missed, and an incompletely
  recorded week that stays `unknown`. Status `attention`.
- **Honest unknowns** (`insufficient_data`). One sample gives no baseline; an unconfirmed
  recording gives no adherence result; an empty window gives no sleep result.

## 8. Reproducing the outputs

From `backend/`, in the Python 3.11 environment:

```powershell
python -m app.scenarios replay sensor_quality_failure --validate
python -m app.scenarios replay progressive_sleep_restriction --validate
python -m app.scenarios replay progressive_sleep_restriction --json --validate   # structured output
```

Over HTTP, the same fixtures give the same statuses and explanations. Three conditions matter:

1. Start the server with the daily sampling interval configured, otherwise window completeness,
   score and the `missing_data` flag are not produced:

   ```powershell
   $env:ORBITVITALS_DATA_QUALITY = '{"expected_intervals":{"sleep_duration":"P1D","sleep_efficiency":"P1D"}}'
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

2. Send the sleep policy in every evaluation command (`sleep_config`). Without it the API
   answers `insufficient_data` with "Sleep screening policy is not configured ... No thresholds
   or physiological findings were assumed." That behaviour was verified and is correct.
3. Fix `evaluated_at` to the checkpoint time so that identifiers and results are deterministic.

Run one worker without `--reload`. A restart erases every record.

Differences between the two routes, both verified:

| | Replay output | HTTP API |
| --- | --- | --- |
| Overall `data_quality` of the evaluation | `not_assessed` | `degraded`, produced by `api_quality_rollup` |
| Structured trend numbers (slope, fitted change, missing nights) | Available in `outputs.sleep_trends` | Only inside the `explanation` text |
| "SIMULATED DATA" prefix | In scenario metadata | At the start of `summary` and every `explanation` |
| Checkpoints | Three steps in one replay | Three evaluation commands with different `window_end` |

## 9. Fallback

If the sleep flow cannot be shown through the interface in time, use physical activity for
Scene B. Its end-to-end HTTP workflow, including a personal baseline, is already documented and
runnable in [frontend-integration.md](../frontend-integration.md): baseline `established` with a
mean of 45 min, later window mean 30 min, deviation -15 min, status `attention`. It has fewer
days and a weaker visual story, so it is the second choice.

Decide by Sunday midday. Do not carry both into the submission demo.
