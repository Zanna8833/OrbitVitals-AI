# Likely judge questions

Hard questions a judge may ask, with short answers that rest on what the repository actually
contains at commit `667f512` (2026-11-14). Each answer names its evidence.

Three rules for answering:

1. Say what is simulated before anyone asks.
2. When the honest answer is "we do not know" or "not yet", say that first and then say what the
   system does instead.
3. Use the wording guide in
   [scientific-evidence-matrix.md](scientific-evidence-matrix.md#5-wording-guide).

## Scientific validity

**1. Is this clinically validated?**
No. It is a research prototype. No algorithm in it has been tested against real astronaut data,
and it does not diagnose. What we can show is that the software does what we say it does,
reproducibly, and that every rule and constant has a stated source or is labelled as our own
choice.
*Evidence:* [algorithm documentation](../../backend/app/algorithms/README.md), limitations
section; evidence matrix item E16.

**2. Where do your thresholds come from?**
There are no clinical thresholds in the system. Its numbers are of three kinds. Definitions: a
duration cannot be negative. Published statistical conventions: the modified z-score factor and
cut-off from the NIST handbook. Settings supplied by the caller: the sleep policy, the exercise
plan and the criteria for an established baseline. The demonstration uses labelled demonstration
values for the third kind. Without a sleep policy the API refuses to screen and answers "No
thresholds or physiological findings were assumed."
*Evidence:* verified over HTTP on 2026-11-14; [frontend-integration.md](../frontend-integration.md).

**3. How do you know that losing fifteen minutes of sleep a night matters medically?**
We do not claim that it does. The sequence is authored to make the rule visible. Our claim is
narrower: the system finds a sustained pattern that meets stated settings and asks a person to
look. Laboratory research on accumulating sleep restriction is the reason we look at trends
across nights, not the source of our settings.
*Evidence:* evidence matrix items E2 and E8.

**4. You report 729 passing tests. What do they prove?**
That the software behaves as specified on inputs we wrote. They prove nothing about physiology or
clinical performance, and we do not present them as validation.
*Evidence:* `python -m pytest`, run on 2026-11-14: 729 passed.

## NASA data

**5. Which NASA data do you use?**
NASA resources, not NASA datasets. The Human Research Program pages on the five hazards and on
specific risks (sleep, fitness, cardiovascular, behavioral) decide which indicators we monitor
and supply the explanations shown next to each finding. NASA's OCHMO-TB-031, which cites
standards written relative to each crew member's own baseline, motivated our personal-reference
design. No NASA dataset is read by any computation. Every measurement is simulated.
*Evidence:* evidence matrix, sections 2 and 4.

**6. The rubric asks for NASA data as a core component. Is yours superficial?**
It is the weakest part of our submission, and we would rather say so. What we can defend: NASA
material is structural in the product. It determines which indicators exist, why each is
explained the way it is, and what the follow-up information says. What we did not do is force an
unrelated dataset into the pipeline to tick a box. Real measurements would enter through the
same ingestion endpoint, which already distinguishes `wearable`, `medical_device`,
`manual_entry` and `simulated` sources.
*Evidence:* [nasa-challenge-alignment.md](nasa-challenge-alignment.md), section 5.

**7. Your cognition code contains NASA astronaut norms. Is that NASA data?**
Those are summary statistics printed in a published NASA Human Research Program study. We
transcribed them correctly, but using numbers from a paper is not dataset integration. That
module is an untested prototype, it is not in the demonstration, and we have not verified that
our test implementation is equivalent to NASA's battery.
*Evidence:* evidence matrix item E15.

## Personalization

**8. Why personal baselines and not normal ranges?**
Because the response to spaceflight differs between people. NASA states that the effects "can
vary substantially between individual astronauts", and NASA's in-mission fitness standards are
written relative to pre-mission values. A ground study of body temperature concluded that "using
any standardized 'normal' temperature will lead to errors for many people".
*Evidence:* evidence matrix item E3.

**9. How many measurements make a baseline reliable?**
We do not know, and the engine does not pretend to. Statistics need at least two values. A
baseline becomes `established` only when criteria supplied by the mission team are met, and
those criteria must name their source. With no criteria every baseline stays `provisional`. The
scenario uses ten samples over nine days as a labelled demonstration setting.
*Evidence:* replay `personalized_baseline`, final checkpoint: the same data falls back to
`provisional` when the policy is removed.

**10. What if the baseline period was itself unusual?**
Then the reference is biased, and that is a real limitation. The engine reports potential
outliers and keeps them visible, marks a reference built from flawed data as `degraded`, and
does not model adaptation within a phase. A person has to judge whether a reference is fit for
use.
*Evidence:* [algorithm documentation](../../backend/app/algorithms/README.md), limitations.

**11. Why a separate baseline for each mission phase?**
Published space-station studies report that group-average blood pressure and core temperature
differ in flight from before flight. A pre-flight reference is therefore not automatically valid
in orbit. The API enforces this: a baseline can only be used for an evaluation in the same
phase.
*Evidence:* evidence matrix item E4. Note that the heart-rate values in our baseline scenario
are authored and are not a claim about adaptation.

## Missing and unreliable measurements

**12. What happens when data is missing?**
Nothing is filled in. Missing nights are named by date, the window is marked `degraded`, and if
too little remains the answer is `insufficient_data`. For exercise, an unrecorded day is
`unknown`, never a missed session.
*Evidence:* replay `progressive_sleep_restriction` and `exercise_adherence_change`.

**13. Can it detect a sensor that drifts, or one that is wrong but plausible?**
No. It detects errors that can be proven from the data: impossible values, duplicates,
inconsistent pairs, future timestamps. Device measuring ranges can be configured, but none are,
because we have no device documentation. Stuck sensors, drift and implausible rates of change
are not implemented, because each would need a threshold we cannot source.
*Evidence:* evidence matrix item E6.

**14. Could the quality check discard a real but extreme value?**
The checks that make a record `unusable` are definitional; a negative duration cannot be real.
A value outside a configured device range is only `degraded`, because it may be real. The
quality engine never flags a value for being high or low, and no record is deleted: it is stored
and labelled.
*Evidence:* [algorithm documentation](../../backend/app/algorithms/README.md), "Decisions open to
review".

## False positives and false negatives

**15. What is your false-positive rate?**
Unknown. We have not measured it, and we have no real data to measure it on. The design limits
false alarms in ways we can show: several conditions must hold at once, there are sufficiency
gates, and the output is "review suggested", not an alarm. There is no calibration and no
correction for looking at many windows.
*Evidence:* [sleep documentation](../../backend/app/domains/sleep/README.md), scientific
limitations.

**16. Could it miss a real problem?**
Yes. Sleep that is uniformly short but stable shows no trend and returns `nominal` unless a
personal baseline is supplied. Abrupt changes can be missed by a trend screen. That is why every
`nominal` result states that it "does not establish adequate sleep or health".
*Evidence:* same document.

## Synthetic data

**17. Why should we trust results on data you wrote yourselves?**
The demonstration shows behaviour, not performance. Expected values are written separately from
the engines and compared with the actual output after execution; a mismatch fails the replay
and is never overwritten. One test changes a fixture to prove that the output changes with it.
We make no accuracy claim.
*Evidence:* [scientific-scenarios.md](../scientific-scenarios.md), verification commands.

**18. Is the simulated data realistic?**
We do not claim that. The sequences are simple and hand-authored, for example a straight decline,
so that the rule is easy to see. They are labelled `simulated` in every record and on every
result.

## Reproducibility

**19. Can I reproduce your demonstration?**
Yes. With Python 3.11 and the pinned requirements, run `python -m app.scenarios replay all
--validate` from `backend/`. It regenerates the fixtures, runs the real engines at fixed times
and compares expected with actual values. There is no randomness, no clock lookup and no network
access. We do not claim identical results across platforms or dependency versions.
*Evidence:* run on 2026-11-14: exit code 0, all checks passed, 765 contract payloads validated.

## Transparency

**20. Where is the AI? Is there a model?**
There is no trained model in the demonstrated pipeline. It is deterministic statistics with
written explanations, by choice: we did not want a black box between an astronaut and their own
data. [The team should state its own plan for the name, for example the planned evidence
assistant, which is not implemented.] SI coding assistants were used to build the software, and
we disclose that in the submission.

**21. How does a user see why a status was assigned?**
Each finding carries an explanation naming the records used and excluded, the rule that fired
and the settings applied, together with the algorithm name and version. The data-quality
assessment has its own notes. The same input always produces the same output.
*Evidence:* any evaluation returned by the API; examples in
[primary-demo-flow.md](primary-demo-flow.md).

## Limitations and fit with the challenge

**22. What are the main limitations?**
Simulated data only. No clinical or flight validation. Demonstration settings, not clinical
thresholds. Only sleep and physical activity are evaluated. The quality engine catches provable
errors only. Storage is in memory. No emergency level exists, so the tool cannot recognise an
emergency.

**23. The challenge asks for guidance on treatments. Where is yours?**
We stop at next steps and human review. We have no validated basis for recommending a treatment,
and a prototype that invented one would be less safe, not more useful. What the tool offers is a
next step matched to the kind of finding, NASA's own published description of what is done about
the risk, and a summary for the flight surgeon. [If the follow-up cards are not built by
submission, say plainly that this part is designed but not implemented.]
*Evidence:* [frontend-demo-mapping.md](frontend-demo-mapping.md#6-follow-up-actions).

**24. The challenge lists blood pressure, heart rate, blood sugar, temperature and mood. You
show sleep.**
We chose depth over breadth. Ingestion, quality checks and personal baselines already work for
all fifteen catalogued metrics; for instance, a blood-pressure reading whose diastolic value
exceeds its systolic value is rejected as unusable today. Evaluation is implemented for sleep,
which the challenge names, and for physical activity. A blood-pressure and temperature
evaluation exists as an early prototype and is not shown.
*Evidence:* `GET /metrics`; HTTP verification of the pressure check on 2026-11-14.

## Practical value for astronauts

**25. What does an astronaut do differently with this tool?**
In the first scene they do not lose sleep, or wake a flight surgeon, over a faulty reading; they
check the device. In the second they notice a slow change they would probably have missed, see
how complete the record is, and share a summary with the ground.

**26. Would it work with a communication delay?**
The engines are pure Python with no network or external service, so nothing in the computation
depends on Earth. That is a property of the design. We have not built or tested an onboard
deployment, and the prototype keeps its data in memory.
*Evidence:* architecture rules in [AGENTS.md](../../AGENTS.md); architecture tests.

**27. Why would an astronaut trust it?**
Because it shows its own uncertainty. It never says "healthy", it names the missing nights, it
explains each result, and it can answer "not enough data".

**28. How is this different from an ordinary health dashboard?**
We make no claim about any particular product. Our design differs from the common
number-to-colour pattern in four ways: a separate data-trust answer, a personal reference for
each mission phase, reasoning over time with the option to decline, and an explanation with the
rule behind every status.

## Process

**29. Did you start before the hackathon?**
No. The first commit is dated 2026-11-14 at 11:07 local time.
*Evidence:* `git log`.

**30. You used SI assistants heavily. What is your own contribution?**
Answer this in the team's own words and truthfully. The rules permit SI tools and require their
use to be described; they also say SI "should not be used to (come up with your idea of how to
solve the challenge)". Be ready to explain the idea, the scientific rules the team set, and the
decisions each member made.
