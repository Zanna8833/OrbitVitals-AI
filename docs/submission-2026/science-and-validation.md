# Scientific methods and validation boundaries

Scope: commit `036df20`, synthetic scenario/HTTP evidence captured for this package.
Implemented methods are distinct from validated medical performance.

## Data Quality Engine

`backend/app/algorithms/data_quality.py` assesses mathematical definitions,
timestamps, duplicate observations, configured acquisition constraints and window
completeness where an expected cadence is supplied. Examples include negative
durations, percentages outside their definitions, durations exceeding the recording
interval and inconsistent paired blood-pressure values. A value is not rejected
merely because it differs from a person's history.

Quality labels describe the data: `not_assessed`, `acceptable`, `degraded` and
`unusable`. They are not physiological findings. `acceptable` means the applied
checks found no problem; it is not a sensor-accuracy certificate. Measuring ranges
and cadence need explicit configuration. The captured default server has no device
ranges or expected sleep sampling intervals, so it cannot establish sensor-range
validity or a numerical Data Quality completeness value for Noor.

No claim is made that this engine detects every artifact, sensor drift, a plausible
but wrong value, or every form of missingness. Its score is not a probability of
clinical correctness.

## Personal Baseline Engine

`backend/app/algorithms/personal_baseline.py` builds a reference for one crew
member, metric and supplied mission phase using admitted-quality observations.
It reports mean, sample standard deviation, median, unscaled median absolute
deviation, minimum and maximum. Potential statistical outliers use the modified
z-score described by NIST; by default they are retained and reported. An unusual
value is not automatically a corrupted record. [NIST outlier reference](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm)

References can be `insufficient_data`, `provisional` or `established`. Establishment
requires caller-supplied count/span criteria; there is no default clinically
justified establishment rule. Noor's demonstration reference is `established`
under an explicitly synthetic policy, using 14 observations spanning 13 days,
with a 480 min median. That status does not establish a medically adequate sleep
duration or a confidence level.

The API requires an eligible selected reference from the same crew member, metric
and phase, with a reference window preceding the evaluation. It does not assume
that a reference from another mission phase is interchangeable. The phase labels
themselves are caller inputs, not a physiological phase-classification algorithm.

## Sleep monitoring and trend analysis

`backend/app/domains/sleep/` supports `sleep_duration` in minutes and
`sleep_efficiency` in percent. It selects unambiguous complete operational nights,
uses actual elapsed time and describes trends with the median of pairwise slopes
(Theil-Sen). Fitted change is the slope multiplied by the observed elapsed span.
The screen also applies explicit sufficiency, coverage, gap, effect-size and
direction-consistency gates. [NIST Theil-Sen reference](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/ts_fit.htm)

All gates in this demonstration are synthetic screening settings. They are not
NASA recommendations, population reference ranges, clinical cutoffs, significance
tests or estimates of diagnostic probability. The module can describe progressive
duration reduction and configured efficiency changes. It does not infer sleep
stages, circadian phase, sleep debt, fatigue, disease, impairment or the cause of a
change. No false-positive rate, sensitivity, specificity or clinical calibration
has been established.

Missing nights are not interpolated. Ambiguous same-night observations and
incomplete intervals have explicit exclusion rules. UTC noon-to-noon buckets are
the seeded operational convention, not a model of a person's biological night.
Robust statistics do not remove bias from small samples, sensor errors or
non-random missingness.

## Noor: what the evidence demonstrates

The selected in-flight reference covers September 28 to October 12, 2026, ending
at 12:00 UTC. The current replay begins October 12 at 12:00 UTC. The nine-night
window ends October 21 at 12:00 UTC; seven recorded durations are 490, 475, 445,
430, 415, 385 and 370 min. October 14 and October 18 night buckets are missing.

| Checkpoint | Included nights | Median (min) | Selected reference (min) | Signed deviation (min) | Sleep-duration result |
| ---------- | --------------- | ------------ | ------------------------ | ---------------------- | --------------------- |
| 2 nights   | 2/2             | 482.5        | 480                      | +2.5                   | `insufficient_data`   |
| 5 nights   | 4/5             | 460          | 480                      | -20                    | `attention`           |
| 9 nights   | 7/9             | 430          | 480                      | -50                    | `attention`           |

The nine-night explanation reports -15 min/day, -120 min fitted change over eight
elapsed days, and decreasing transition fraction 1. The configured absolute
baseline-deviation threshold of 60 min is not met by the 50 min window-median
difference. The trend criterion prompts attention; the baseline comparison is
additional context. The first result remains insufficient despite a computable
slope and descriptive baseline deviation.

In this captured API configuration, the per-metric quality is `acceptable` at all
three checkpoints and `completeness` is null. The sleep domain separately describes
7/9 night coverage and missing dates. Do not relabel those as a degraded Data
Quality assessment or a 78% quality/confidence score. Configuring a daily cadence
can change quality outputs; a new run must then be captured and labelled separately.

A deliberately corrupt Chen scenario provides the contrast: the early sleep
evaluation is `nominal` with `degraded` quality, not an emergency. Quality failure
and physiological screening are independent answers.

## Physical activity

The implemented module compares usable records and complete daily totals with
explicitly configured demonstration targets and personal references. It represents
planned rest, incomplete records and missing coverage separately. Minutes and
kilocalories do not establish exercise intensity, fitness, adequate loading or
medical adherence. Structured daily-adherence diagnostics are not a public HTTP
resource; the API exposes `EvaluationResult` and its explanations.

## Innovation claim and evidence boundary

The project combines quality assessment, personal reference, longitudinal screening
and traceable explanations in a reproducible workflow. It does not introduce a new
statistical estimator or demonstrate a validated medical AI. It aims to support
inspection and human review. Any benefit to health, decision quality, workload or
alarm burden requires future evaluation.

## Validation levels

| Level                    | Current evidence                                           | What it does not establish                          |
| ------------------------ | ---------------------------------------------------------- | --------------------------------------------------- |
| Contract verification    | Pydantic/JSON Schema validation and canonical units        | Truth of an observation                             |
| Software tests           | Deterministic unit, architecture, scenario and HTTP checks | Clinical validity or measured sensor accuracy       |
| Synthetic demonstrations | Repeatable patterns, gaps and unsuitable inputs            | Generalization to astronaut populations             |
| Bridge integration       | Actual stored payloads retrieved and validated over HTTP   | Acceptance of the approved visual design            |
| Demo 6 visual acceptance | Pending matching source and browser comparison             | Must not be reported as passed                      |
| Real-world validation    | Not demonstrated                                           | No astronaut outcome, diagnostic or treatment claim |

Future work requires authorized real or analog data, acquisition-context and
device validation, policy selection with domain experts, prospective evaluation,
human-factors testing, security/privacy review and independent assessment of any
AI-generated guidance. A trained model, retrieval system or external dataset must
be evaluated separately before inclusion in the scientific claims.
