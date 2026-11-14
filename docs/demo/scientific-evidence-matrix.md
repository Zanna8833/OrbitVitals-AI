# Scientific evidence matrix

A claim-by-claim audit of what OrbitVitals AI can say in front of judges, what each statement
rests on, and where the evidence stops.

Repository state assessed: commit `667f512` (2026-11-14). OrbitVitals AI is a research
prototype. No algorithm in it has been validated against real astronaut data.

## 1. How to read this document

**Evidence classes.** Every claim is labelled with what kind of support it has.

| Label | Meaning |
| --- | --- |
| NASA resource | A NASA page or technical brief that informs the design or gives context |
| Literature | Published research that informs an algorithm or a constant |
| Definition | True by the definition of the metric or by arithmetic; needs no study |
| Design choice | An engineering decision made by the team, with no external source |
| Synthetic | Hand-authored demonstration data or demonstration settings |
| Gap | Needs evidence or implementation before it can be claimed |

**Source verification.** Each source was checked during this audit, on 2026-11-14.

| Level | Meaning |
| --- | --- |
| Primary | The cited passage was read in the original page or the open-access full text |
| Abstract | Confirmed from the abstract or the publisher's summary, not the full text |
| Not verified | Bibliographic details taken from the code or from memory; not re-checked |

## 2. Data provenance statement

Use this paragraph, or a shorter form of it, wherever data sources are described.

> Every measurement shown by OrbitVitals AI is synthetic and carries `source: "simulated"`. No
> NASA or Space Agency Partner dataset is read by any computation in the demonstration. NASA
> Human Research Program pages and published spaceflight studies inform which indicators we
> monitor and how we interpret them. All detection settings in the demonstration are labelled
> demonstration values, not clinical thresholds.

| Category | What it covers in this project |
| --- | --- |
| Real NASA or partner datasets used in computations | **None** |
| Published statistics from astronaut studies used in a computation | Two prototypes outside the demonstrated pipeline: cognition norms from Dev et al. 2024 (E15) and group-level in-flight changes from Norsk et al. 2015 and Stahn et al. 2017 (E11, E13). Using numbers printed in a paper is not dataset integration |
| Published research informing an algorithm | Modified z-score (E7), Theil-Sen slope (E8) |
| NASA resources informing design and context | HRP hazards and risks pages, OCHMO-TB-031 (E1, E3, E5, section 4) |
| Synthetic demonstration datasets | All five replay scenarios and every HTTP example |
| Assumptions chosen for demonstration | Sleep screening policy, baseline establishment criteria, exercise targets, sampling intervals |
| Features that still need evidence or implementation | Vital-signs and cognition evaluation, follow-up guidance, device ranges, false-positive characterisation |

## 3. Claim-to-evidence matrix

### Summary

| ID | Claim in brief | Evidence class | Source check | Safe to present |
| --- | --- | --- | --- | --- |
| E1 | ISS crews have slept less than scheduled; NASA lists sleep as a risk | NASA resource, Literature | Primary, Abstract | Yes, as context |
| E2 | Modest sleep restriction accumulates and is under-perceived | Literature | Abstract | Yes, as motivation only |
| E3 | Responses to spaceflight differ between individuals | NASA resource, Literature | Primary | Yes |
| E4 | Some indicators differ in flight, so references are kept per phase | Literature | Primary | Yes, with one caveat |
| E5 | Exercise is NASA's main countermeasure; adherence matters | NASA resource | Primary | Yes; demonstration targets are fictional |
| E6 | Quality checks flag provably wrong records, never unusual ones | Definition | Not applicable | Yes, with stated scope |
| E7 | Potential outliers are screened with the modified z-score | Literature | Primary | Yes |
| E8 | Sleep trends use the Theil-Sen slope plus explicit gates | Literature, Design choice | Primary | Yes; gates are demonstration settings |
| E9 | Activity review uses transparent arithmetic; kcal treated with caution | Design choice, Literature | Abstract | Yes |
| E10 | A statistical deviation is never labelled an emergency | Design choice | Verified in code and tests | Yes |
| E11 | Expected in-flight blood-pressure band | Literature, Gap | Primary, Abstract | Not as a feature |
| E12 | 5 mmHg blood-pressure margin from ISO 81060-2 | Literature | Not verified | **No** as currently justified |
| E13 | Expected in-flight temperature rise | Literature, Gap | Primary | Not as a feature |
| E14 | 0.3 degC margin and the 3-SD rule | Literature, Design choice | Primary | **No** as currently worded |
| E15 | Cognition scores against published astronaut norms | Literature, Gap | Primary | Only as a prototype, with caveats |
| E16 | 729 automated tests pass; replay is reproducible | Verified by execution | Run on 2026-11-14 | Yes, as software verification |
| E17 | All demonstration data and settings are synthetic | Synthetic | Verified in outputs | Yes; must always be stated |

### Group A. Why the problem matters

#### E1. Sleep in spaceflight

- **Claim.** Crews on the International Space Station have slept markedly less than scheduled,
  and NASA treats inadequate sleep as a human-system risk.
- **Phenomenon.** Sleep loss, circadian desynchronisation and work overload.
- **Evidence.** NASA, *Risk from Inadequate Sleep and Irregular Schedules*: "Astronauts are
  exposed to numerous stressors during spaceflight, such as work overload, irregular light-dark
  cycles, and sleep-pattern disruptions." Barger et al. 2014 report a mean in-flight sleep
  duration of 6.09 hours on ISS missions against 8.5 hours scheduled.
- **Does the source support it?** Yes. The NASA page was read directly. The Barger figures were
  confirmed from the publishing hospital's press release and news coverage, not the full text.
- **Implementation.** Motivates the sleep domain (`backend/app/domains/sleep/`). No number from
  these sources is used in code.
- **Assumptions introduced.** None.
- **Limitations.** Group averages from past missions, measured by wrist actigraphy and diaries.
  They do not define adequate sleep for an individual.
- **Wording for the demonstration.** "A study of space-station crews found they averaged about
  six hours of sleep when eight and a half were scheduled. NASA lists inadequate sleep among its
  human spaceflight risks. That is why sleep is our first indicator."
- **Safe to present.** Yes, as context.

#### E2. Accumulating sleep loss

- **Claim.** Modest nightly sleep restriction accumulates into measurable performance deficits
  that people tend not to notice in themselves, so a trend across nights is more informative than
  any single night.
- **Phenomenon.** Chronic sleep restriction.
- **Evidence.** Van Dongen et al. 2003: 14 days at 4 or 6 hours in bed produced cumulative,
  dose-dependent deficits; "sleepiness ratings suggest that subjects were largely unaware of
  these increasing cognitive deficits".
- **Does the source support it?** Yes for the motivation. Confirmed at abstract level.
- **Implementation.** Motivates screening a window of nights (`sleep/trends.py`). The algorithm's
  gates are not derived from this study.
- **Assumptions introduced.** That a declining duration trend is worth a person's attention.
- **Limitations.** A ground laboratory study of healthy volunteers. Our algorithm does not
  estimate sleep debt, performance or risk.
- **Wording.** "Laboratory research shows that small nightly shortfalls add up, and that people
  underestimate the effect. Our sleep screen looks for the pattern across nights."
- **Safe to present.** Yes, as motivation. Do not say the system "detects sleep debt" or
  "predicts impairment".

#### E3. Individual differences and personal references

- **Claim.** The body's response to spaceflight varies substantially between people, so each
  crew member is compared with their own reference rather than with a population range.
- **Phenomenon.** Inter-individual variability.
- **Evidence.**
  - NASA, *Risk of Reduced Cardiorespiratory and Musculoskeletal Fitness*: "The effects of
    exposure to microgravity can vary substantially between individual astronauts." The same
    page reports that "between 12-38% of space station crew members lose more than 20% of their
    pre-mission fitness".
  - NASA OCHMO-TB-031: "The extent of physiological deconditioning varies per individual and is
    dependent on a multitude of factors such as starting fitness level, age, mission duration,
    and gravity level." The brief also quotes NASA-STD-3001 requirements that are written
    relative to each person's own values, for example "[V1 4024] Countermeasures shall maintain
    in-mission skeletal muscle strength at or above 80% of baseline values."
  - Diamond et al. 2021 (96 adults, oral temperature): individual mean temperatures ranged from
    35.2 to 37.4 degC, and "using any standardized 'normal' temperature will lead to errors for
    many people".
- **Does the source support it?** Yes, for the principle. All three were read in the original.
  None of them validates our baseline statistics or any deviation threshold.
- **Implementation.** `backend/app/algorithms/personal_baseline.py`: mean, sample standard
  deviation, median, MAD, minimum and maximum per crew member, metric and mission phase.
- **Assumptions introduced.** Values within a phase are treated as one population. The criteria
  for an `established` baseline are supplied by the caller and are demonstration settings.
- **Limitations.** Diamond et al. is a ground study. The NASA statements concern fitness. A
  baseline built from few samples is itself uncertain. Adaptation within a phase is not modelled.
- **Wording.** "NASA's own in-mission fitness standards are written relative to each crew
  member's pre-mission values. We apply the same principle to every indicator: compare a person
  with themselves."
- **Safe to present.** Yes.

#### E4. Mission phase changes the reference

- **Claim.** Some indicators differ in flight from before flight at group level, so a reference
  is kept separately for each mission phase.
- **Phenomenon.** Physiological adaptation to long-duration spaceflight.
- **Evidence.** Norsk et al. 2015 (eight male astronauts, one in-flight session between days 85
  and 192): 24-hour average systolic, diastolic and mean arterial pressures "were reduced by
  8 ± 2 mmHg", "9 ± 2 mmHg" and "10 ± 3 mmHg"; "heart rate and catecholamine concentrations were
  unchanged". Stahn et al. 2017 (eleven astronauts): resting core body temperature showed an
  "increase of about 1 °C developed gradually over 2.5 months".
- **Does the source support it?** Yes, for blood pressure and core temperature at group level.
  Both were read in the original.
- **Implementation.** Phase-specific baselines in `personal_baseline.py`. The API also refuses to
  compare across phases: a selected baseline must have the same mission phase as the evaluation
  (`backend/app/services/integration.py`).
- **Assumptions introduced.** Phase boundaries are supplied by the caller. A phase is treated as
  homogeneous.
- **Limitations.** Small samples. Hughson et al. 2012 reported no in-flight change in markers of
  cardiovascular stability, so findings are not uniform. No source here covers heart rate or
  sleep shifting by phase.
- **Caveat for the demonstration.** The replay scenario `personalized_baseline` shows a
  heart-rate median of 58 bpm before flight and 64 bpm in flight. Those numbers are authored
  fixtures. Norsk et al. reported unchanged heart rate. Present the scenario as "references are
  kept per phase", never as an expected adaptation.
- **Wording.** "Published space-station studies report that average blood pressure and core
  temperature differ in orbit from before launch. A pre-flight reference is therefore not
  automatically the right one in flight, so we keep one reference per mission phase."
- **Safe to present.** Yes, with the caveat above.

#### E5. Exercise as a countermeasure

- **Claim.** Exercise is NASA's main countermeasure against deconditioning, so adherence to a
  personal exercise plan is worth monitoring.
- **Phenomenon.** Loss of aerobic fitness, muscle strength and bone in microgravity.
- **Evidence.** NASA, *Risk of Reduced Cardiorespiratory and Musculoskeletal Fitness*: "Six to
  seven days a week, astronauts on the International Space Station perform resistance training
  and aerobic exercises for 1.5 hours per day". NASA OCHMO-TB-031 lists in-flight training time
  prescriptions of "Approximately 30 minutes of interval or steady-state exercise" and "30-60
  minutes load-bearing training".
- **Does the source support it?** Yes, as context. Both read in the original.
- **Implementation.** `backend/app/domains/physical_activity/`.
- **Assumptions introduced.** The demonstration targets (40 min and 200 kcal per day) are
  fictional plan values. They are not taken from NASA.
- **Limitations.** Minutes and active kilocalories say nothing about intensity, loading or
  exercise type.
- **Wording.** "NASA describes exercise as the daily countermeasure against muscle, bone and
  fitness loss. We check recorded activity against the crew member's own plan and flag
  sustained reductions for review."
- **Safe to present.** Yes, if the targets are labelled as simulated plan values.

### Group B. Algorithms in the demonstrated pipeline

#### E6. Data quality checks

- **Claim.** The Data Quality Engine flags records that are provably wrong and never flags a
  value merely for being high, low or unusual.
- **Phenomenon.** Acquisition errors and missing observations.
- **Evidence.** Definitions. A duration, count, amount or mass cannot be negative; a percentage
  share lies between 0 and 100; a sleep or exercise duration cannot exceed its observation
  interval; diastolic pressure cannot exceed the systolic pressure of the same reading; a
  timestamp cannot lie after the assessment time; redundant copies are duplicates.
- **Does the source support it?** These are definitional and need no study.
- **Implementation.** `backend/app/algorithms/data_quality.py`. Verified over HTTP on 2026-11-14:
  a reading of 78/121 mmHg entered as systolic/diastolic is returned `unusable` with the note
  "Diastolic blood pressure (121 mmHg) is higher than the systolic blood pressure of the same
  reading (78 mmHg), which contradicts their definitions; neither value is used."
- **Assumptions introduced.** The rule that identifies two records as the same observation. The
  descriptive `score` proportion has no external source. Expected sampling intervals are
  configuration, not facts.
- **Limitations.** No device measuring range is configured, so `out_of_sensor_range` is never
  raised. The engine does not detect stuck sensors, drift, implausible rates of change,
  disagreement between devices, or values that are plausible but wrong. `acceptable` means only
  that no applied check found a problem.
- **Wording.** "The quality engine catches errors that can be proven from the data itself, and it
  reports missing observations. It does not yet detect subtle sensor drift."
- **Safe to present.** Yes, with that scope.

#### E7. Potential outliers

- **Claim.** Potential outliers in a baseline are identified with the modified z-score, using
  the factor 0.6745 and the cut-off 3.5, and are reported rather than silently removed.
- **Evidence.** Iglewicz and Hoaglin, as given in the NIST/SEMATECH e-Handbook, section
  1.3.5.17: "These authors recommend that modified Z-scores with an absolute value of greater
  than 3.5 be labeled as potential outliers."
- **Does the source support it?** Yes. The NIST page was read directly.
- **Implementation.** `backend/app/algorithms/robust_statistics.py`.
- **Assumptions introduced.** Approximate normality of the reference values. Keeping potential
  outliers by default is a team decision.
- **Limitations.** Unreliable for very small samples. Skipped when the MAD is zero.
- **Wording.** "We use a standard robust statistic from the NIST handbook to point out unusual
  reference values, and we keep them visible."
- **Safe to present.** Yes.

#### E8. Sleep trend screening

- **Claim.** Sleep trends are described with the Theil-Sen slope over actual elapsed time, and a
  trend is reported only when explicit sufficiency and effect-size gates are met.
- **Evidence.** NIST Dataplot reference manual, *Theil-Sen fit*: "Theil-Sen regression is a
  non-parametric method ... It is robust against outliers". Read directly.
- **Does the source support it?** Yes for the estimator. The gates are project rules and are
  documented as such in the [sleep module documentation](../../backend/app/domains/sleep/README.md).
- **Implementation.** `backend/app/domains/sleep/trends.py` and `evaluation.py`.
- **Assumptions introduced.** The demonstration policy: at least four nights, coverage of 0.6,
  three elapsed days, a slope of 5 min/day, a fitted change of 30 min and a decreasing-transition
  fraction of 0.75. These are hand-authored demonstration settings with no clinical meaning.
- **Limitations.** Not a significance test. No confidence interval is computed. It describes a
  roughly linear tendency over a short window and can miss abrupt changes. Missing nights may be
  informative in themselves.
- **Wording.** "We fit a robust slope through the nights that were actually recorded and flag it
  only when it passes settings chosen for this demonstration. It is a screen that asks for human
  review, not a statistical test."
- **Safe to present.** Yes.

#### E9. Physical activity review

- **Claim.** Activity review uses transparent arithmetic: daily and weekly sums, comparison with
  a supplied personal plan, and runs of strictly decreasing totals. Energy estimates are treated
  with caution.
- **Evidence.** The rules are design choices, documented in
  [physical-activity-monitoring.md](../physical-activity-monitoring.md). Shcherbina et al. 2017
  tested seven wrist devices against indirect calorimetry: "No device achieved an error in EE
  below 20 percent."
- **Does the source support it?** It supports caution about energy estimates. Confirmed at
  abstract level. It is a ground study and sets no error bound for spaceflight.
- **Implementation.** `backend/app/domains/physical_activity/`. Energy is never derived from
  minutes.
- **Assumptions introduced.** A run of three decreasing totals is a descriptive convention.
  Recording completeness must be confirmed by the caller.
- **Limitations.** No noise model, no significance, no validated link to deconditioning.
- **Wording.** "We compare recorded exercise with the crew member's own plan and point out
  sustained reductions. A missing record is shown as unknown, never as a missed session."
- **Safe to present.** Yes.

#### E10. A deviation is not an emergency

- **Claim.** The system never turns a statistical deviation or a data problem into a medical
  emergency.
- **Evidence.** Code and tests. The sleep and activity modules never emit `alert` ("no evidence
  supports a clinical escalation rule"). Each replay scenario includes the check
  `no_emergency_label`, and all pass.
- **Implementation.** Status mapping in the sleep and activity modules; the separation of
  `DataQuality` from `EvaluationStatus` in [api-contracts.md](../api-contracts.md).
- **Limitations.** The reverse also holds: the system cannot recognise a real emergency. It is a
  review aid.
- **Wording.** "`attention` means a person should look at this. `nominal` means no configured
  signal was found; it does not mean healthy. The prototype has no emergency level because we
  have no validated basis for one."
- **Safe to present.** Yes.

### Group C. Prototypes outside the demonstrated pipeline

The code for E11 to E15 is in the repository but is not reachable through the API (a
`vital_signs` evaluation request returns 422), is not part of any replay scenario, and has no
automated tests. Treat these as work in progress.

#### E11. Expected in-flight blood-pressure band

- **Claim in the code.** In flight, blood pressure "equal to or up to about 10 mmHg below the
  pre-flight baseline is expected".
- **Evidence.** Norsk et al. 2015 (values in E4). Hughson et al. 2012 is cited for "no change at
  rest".
- **Does the source support it?** Partly. Norsk et al. report a shift in a 24-hour ambulatory
  average, in eight men, at one time point. The code applies it as an allowed band for a single
  latest reading. For Hughson et al., only the abstract-level conclusion ("no change in markers
  of cardiovascular stability during long-duration spaceflight") was confirmed; the specific
  statement about resting pressure was not checked in the full text.
- **Implementation.** `backend/app/domains/vitals/vitals.py`, `BP_EXPECTED_DROP = 10`.
- **Assumptions introduced.** A group mean shift applies to every individual. A single reading is
  comparable with a 24-hour average. The shift applies in full from the first mission day and
  equally to systolic and diastolic values.
- **Limitations.** Small all-male sample, mixed literature, no tests, not integrated.
- **Wording, if mentioned at all.** "We are prototyping a blood-pressure check that shifts the
  crew member's pre-flight reference by the group-level change published for ISS crews. It is not
  part of today's demonstration."
- **Safe to present.** Not as a working feature.

#### E12. Blood-pressure measurement margin

- **Claim in the code.** "BP monitors are validated for a mean error up to 5 mmHg (ISO 81060-2,
  Stergiou et al. 2018)", used as a ±5 mmHg margin on each reading.
- **Evidence.** Stergiou et al. 2018. The paper's existence and scope were confirmed. Its
  numerical criterion was not re-read during this audit. It is commonly reported as a mean
  difference within 5 mmHg **with a standard deviation within 8 mmHg** across a validation
  cohort.
- **Does the source support it?** No, not as used. The criterion bounds the average error of a
  device over many people. It is not an accuracy bound for one reading, which can differ from
  the reference by considerably more.
- **Recommendation to the module owner.** Describe the 5 mmHg as an engineering margin, or
  replace it with a justified per-reading tolerance. Do not cite the standard as its source.
- **Safe to present.** No.

#### E13. Expected in-flight temperature rise

- **Claim in the code.** Resting core temperature rises by about 1 degC, gradually, reaching a
  plateau after about 75 days.
- **Evidence.** Stahn et al. 2017 (values in E4), read in the original.
- **Does the source support it?** Yes for the magnitude and the time scale. The linear ramp is
  the team's assumption, as the code comment states.
- **Implementation.** `vitals.py`, `TEMP_EXPECTED_RISE = 1.0`, `TEMP_RISE_DAYS = 75`.
- **Assumptions introduced.** A linear rise. A group mean applies to every individual. The
  study measured core temperature at rest with a forehead heat-flux sensor; our
  `body_temperature` metric does not specify a measurement site.
- **Limitations.** Eleven astronauts, one sensor technology, no tests, not integrated.
- **Safe to present.** Not as a working feature.

#### E14. Temperature margin and the three-standard-deviation rule

- **Claims in the code.** "Day-to-day variability of body temperature in healthy adults:
  0.32 degC", used as a 0.3 degC margin; and "with one reading per day, 2 standard deviations
  gave a false alarm about every 20 days for healthy crew, so the limit is 3".
- **Evidence.** Diamond et al. 2021: "The mean standard deviation across an individual's 14
  temperature readings was only 0.32°C". Read in the original.
- **Does the source support it?** The 0.32 degC figure is correct, for oral temperature in 96
  adults on the ground. The "false alarm" sentence is not an observation: the repository holds no
  crew data. It restates a property of the normal distribution, under which about 4.6% of values
  lie beyond two standard deviations (roughly one reading in 22) and about 0.3% beyond three.
- **Our calculation, for the module owner.** A margin of 0.3 degC is about one within-person
  standard deviation. If the Diamond figure applied, ordinary variation alone would put roughly
  one reading in six below the lower bound. The band is therefore likely to produce frequent
  `attention` results in a person with no change.
- **Recommendation.** Reword the comment as a theoretical expectation, and widen or justify the
  margin before the module is used.
- **Safe to present.** No, as currently worded.

#### E15. Cognition scores against astronaut norms

- **Claim in the code.** Test scores are converted to z-scores using pre-flight means and
  standard deviations of 25 NASA astronauts, and a score with z at or below -1.5 is listed as
  low.
- **Evidence.** Dev et al. 2024, Table 1 and Methods; scoring rules from Basner et al. 2021.
- **Does the source support it?** The numbers are transcribed correctly. All 19 pairs of mean
  and standard deviation in `NORMS` match Table 1, and the cut-off is the paper's ("z ≤ −1.5"). The scoring rules
  (Motor Praxis 50-pixel scaling, Line Orientation clicks, the 355 ms lapse and 100 ms
  false-start thresholds, speed as 10 minus the reciprocal response time, efficiency as the mean
  of speed and accuracy) match Basner et al. 2021. Both read in the original.
- **Implementation.** `backend/app/domains/cognition/cognition.py`, a standalone command-line
  scorer.
- **Assumptions introduced.** The norms were collected with NASA's Cognition battery. Our tests
  are an emulation, so equivalence of stimuli, timing and hardware is unverified. Dev et al.
  "corrected for practice effects"; our code states that it does not.
- **Limitations.** The authors call their table preliminary (24 or 25 data points per test).
  Their conclusion is that there was "no evidence for a systematic decline in cognitive
  performance", and "11.8% of all flight and post-flight scores were at or below 1.5 standard
  deviations below the sample's baseline mean". A low score is therefore common in healthy
  astronauts and is not evidence of impairment. No tests, no API, and the test-taking interface
  is not in the repository.
- **Why it matters.** This is the only place in the repository where numbers derived from real
  astronauts enter a computation. It is still a literature value, not dataset integration.
- **Wording.** "A prototype scores our cognitive tests against pre-flight norms that NASA
  researchers published for 25 astronauts. We have not verified that our test implementation is
  equivalent to NASA's battery, so these scores are for research discussion only."
- **Safe to present.** Only as a prototype, with those caveats.

### Group D. Claims about the project itself

#### E16. Tests and reproducibility

- **Claim.** The backend passes 729 automated tests, and the five scenarios replay
  deterministically.
- **Evidence.** Executed on 2026-11-14 at commit `667f512`: `python -m pytest` reported
  "729 passed"; `ruff check` and `ruff format --check` passed; `python -m scripts.export_schemas
  --check` reported the schemas up to date; `python -m app.scenarios replay all --validate`
  exited with 0, every expectation passed and 765 embedded contract payloads validated.
- **Limitations.** Tests show that the software does what the team specified, on authored
  fixtures. They say nothing about physiological or clinical correctness. Reproducibility across
  platforms and dependency versions is not claimed.
- **Wording.** "729 automated tests verify the software's behaviour. They are not scientific
  validation, and we do not present them as such."
- **Safe to present.** Yes, in exactly that form.

#### E17. Synthetic data

- **Claim.** Every value, identifier, target and threshold in the demonstration is synthetic.
- **Evidence.** Every measurement in the replay outputs has `source: "simulated"`; evaluation
  summaries and explanations begin with "SIMULATED DATA"; the scenario documentation states that
  fixtures are "engineering choices that exercise the software".
- **Wording.** "All crew data here is simulated and labelled as such on every screen."
- **Safe to present.** Yes. It must be stated early and stay visible.

## 4. NASA hazards and risks behind each indicator

Prepared content for the challenge questions "Why is an exam needed?" and "How do spaceflight
hazards affect these health indicators?". Quotations are verbatim from NASA pages read on
2026-11-14. The pairing of an indicator with a hazard is our own reading of those pages.

| Indicator | State in OrbitVitals AI | NASA risk | NASA's description | What NASA says can be done |
| --- | --- | --- | --- | --- |
| Sleep duration, sleep efficiency | Evaluated | [Risk from Inadequate Sleep and Irregular Schedules](https://www.nasa.gov/reference/risk-from-inadequate-sleep-and-irregular-schedules/) | "Astronauts are exposed to numerous stressors during spaceflight, such as work overload, irregular light-dark cycles, and sleep-pattern disruptions." | "light-emitting diodes, or LEDs, simulate Earth's light-dark cycle to help astronauts sleep better"; "Astronauts are also given designated times for relaxation and self-care" |
| Exercise duration, active energy | Evaluated | [Risk of Reduced Cardiorespiratory and Musculoskeletal Fitness](https://www.nasa.gov/reference/risk-of-reduced-cardiorespiratory-and-musculoskeletal-fitness/) | "Living in microgravity can weaken the bones, muscles, and cardiopulmonary systems of astronauts" | "Six to seven days a week, astronauts ... perform resistance training and aerobic exercises for 1.5 hours per day"; "Crew members also undergo periodic fitness self-evaluations" |
| Blood pressure, heart rate | Baseline and quality checks only; evaluation is a prototype | [Risk of Cardiovascular Adaptations](https://www.nasa.gov/reference/risk-of-cardiovascular-adaptations/) | "Low-gravity conditions and other spaceflight stressors can alter the heart and blood vessels" | "Regular exercise and healthy diets help crews maintain cardiovascular fitness." |
| Cognitive test performance | Standalone prototype | [Risk of Behavioral Changes and Psychiatric Disorders](https://www.nasa.gov/reference/risk-of-behavioral-conditions-and-psychiatric-disorders/) | "The prolonged isolation and confinement that astronauts face in space can increase risks of behavioral issues and psychiatric disorders"; "These factors may impact a crew member's sleep, morale, and decision making" | "NASA encourages astronauts to explore self-care options including keeping a regular journal." |

The hazard that motivates the whole product is **distance from Earth**. NASA: "Instructions, new
supplies, medical care, and more become increasingly challenging to receive from Earth as
astronauts venture deeper into space", and "Planning and self-sufficiency will be key to
successful deep space missions." ([5 Hazards of Human Spaceflight](https://www.nasa.gov/hrp/hazards/))
A crew member who must judge a reading alone first needs to know whether the reading can be
trusted.

## 5. Wording guide

| Say | Do not say |
| --- | --- |
| "review suggested", "a person should look at this" | "alert", "emergency", "diagnosis" |
| "no configured signal found" | "healthy", "normal", "all clear" |
| "personal reference for this mission phase" | "normal range" |
| "demonstration settings" | "clinical thresholds", "NASA thresholds" |
| "informed by NASA Human Research Program resources and published ISS studies" | "uses NASA data", "trained on NASA data", "NASA-validated" |
| "simulated crew data" | "astronaut data", "mission data" |
| "729 automated tests verify software behaviour" | "validated", "proven", "clinically tested" |
| "transparent statistics; every result explains itself" | "the AI detects", "the model predicts" |
| "prototype, not yet integrated" (vital signs, cognition) | "we also monitor blood pressure, temperature and cognition" |
| "the quality engine catches provable errors" | "detects sensor failures" without qualification |

The demonstrated pipeline contains no trained model. It is deterministic statistics with
written explanations. If the product name raises the question, say so plainly.

## 6. Verification limitations

- PubMed pages could not be opened during this audit. Barger et al. 2014, Van Dongen et al.
  2003, Shcherbina et al. 2017 and Hughson et al. 2012 were confirmed from abstracts and
  publisher summaries returned by search, not from full text.
- The numerical criterion of ISO 81060-2 was not re-read (E12).
- Basner et al. 2015 and Basner et al. 2020, both cited in `cognition.py`, were not opened. They
  are cited by the two papers that were read.
- No attempt was made to locate or assess real astronaut datasets beyond confirming that NASA's
  Open Science Data Repository exists. No statement is made here about what such data contains.
- This audit covers the claims a presentation is likely to make. It is not a code review.

## 7. Reference list

Sources used by the project, in a form suitable for the References field of the submission.

NASA resources

- NASA Human Research Program. *5 Hazards of Human Spaceflight.* <https://www.nasa.gov/hrp/hazards/>
- NASA Human Research Program. *Risks of Human Spaceflight.* <https://www.nasa.gov/hrp/risks/>
- NASA. *Risk from Inadequate Sleep and Irregular Schedules.* <https://www.nasa.gov/reference/risk-from-inadequate-sleep-and-irregular-schedules/>
- NASA. *Risk of Reduced Cardiorespiratory and Musculoskeletal Fitness.* <https://www.nasa.gov/reference/risk-of-reduced-cardiorespiratory-and-musculoskeletal-fitness/>
- NASA. *Risk of Cardiovascular Adaptations.* <https://www.nasa.gov/reference/risk-of-cardiovascular-adaptations/>
- NASA. *Risk of Behavioral Changes and Psychiatric Disorders.* <https://www.nasa.gov/reference/risk-of-behavioral-conditions-and-psychiatric-disorders/>
- NASA Office of the Chief Health and Medical Officer. *OCHMO-TB-031 Exercise Overview.* <https://www.nasa.gov/ochmo-tb-031-exercise-overview-2/>

Published research

- Barger LK, et al. Prevalence of sleep deficiency and use of hypnotic drugs in astronauts
  before, during, and after spaceflight. *Lancet Neurology* 2014;13:904-912.
- Basner M, et al. Continuous and intermittent artificial gravity as a countermeasure to the
  cognitive effects of 60 days of head-down tilt bed rest. *Frontiers in Physiology*
  2021;12:643854. <https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2021.643854/full>
- Dev SI, et al. Cognitive performance in ISS astronauts on 6-month low earth orbit missions.
  *Frontiers in Physiology* 2024;15:1451269. <https://pmc.ncbi.nlm.nih.gov/articles/PMC11614644/>
- Diamond A, et al. One size does not fit all: assuming the same normal body temperature for
  everyone is not justified. *PLoS One* 2021. <https://pmc.ncbi.nlm.nih.gov/articles/PMC7857558/>
- Hughson RL, et al. Cardiovascular regulation during long-duration spaceflights to the
  International Space Station. *Journal of Applied Physiology* 2012;112:719-727.
- Norsk P, et al. Fluid shifts, vasodilatation and ambulatory blood pressure reduction during
  long duration spaceflight. *Journal of Physiology* 2015;593:573-584.
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC4324706/>
- Shcherbina A, et al. Accuracy in wrist-worn, sensor-based measurements of heart rate and
  energy expenditure in a diverse cohort. *Journal of Personalized Medicine* 2017;7:3.
  <https://pubmed.ncbi.nlm.nih.gov/28538708/>
- Stahn AC, et al. Increased core body temperature in astronauts during long-duration space
  missions. *Scientific Reports* 2017;7:16180. <https://pmc.ncbi.nlm.nih.gov/articles/PMC5701078/>
- Stergiou GS, et al. A universal standard for the validation of blood pressure measuring
  devices. *Hypertension* 2018;71:368-374.
- Van Dongen HPA, et al. The cumulative cost of additional wakefulness. *Sleep*
  2003;26:117-126. <https://pubmed.ncbi.nlm.nih.gov/12683469/>

Statistical references

- NIST/SEMATECH e-Handbook of Statistical Methods, section 1.3.5.17, Detection of Outliers.
  <https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm>
- NIST Dataplot Reference Manual, Theil-Sen fit.
  <https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/ts_fit.htm>

Also list in the submission every software dependency in `backend/requirements*.txt`, the
frontend dependencies, and any image, icon or font used by the interface or the slides.
