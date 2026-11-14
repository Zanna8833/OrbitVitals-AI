# Presentation storyboards

The product narrative, two internal demonstrations, the submission-compliant demo in both
permitted formats, drafts for the project page, and a plain-language account of the algorithms.

Backend behaviour quoted here was verified on 2026-11-14 at commit `667f512`. The interface is
not in this repository, so every screen direction is a plan. All data is **simulated**.

## A. Core product narrative

**Tagline.** Know what to trust, what changed, and what to do next.

**One sentence.** OrbitVitals AI is an explainable health-monitoring prototype that tells an
astronaut three things a number-to-colour dashboard blurs together: whether a measurement can be
trusted, what their own reference is in this mission phase, and whether a change over time
deserves a person's attention.

**Sixty words.** Far from Earth, astronauts must judge their own health data. A reading can
mislead in two ways: a faulty measurement can look alarming, and a slow real change can look
fine. OrbitVitals AI checks data quality first, compares each person with themselves, follows
trends over time, explains every result in words, and says "not enough data" when that is the
truth.

**The problem.** NASA's challenge states that "astronauts carry much of the responsibility for
spotting these changes in themselves". NASA's Human Research Program names distance from Earth
as a hazard because "medical care, and more become increasingly challenging to receive". A crew
member acting alone on a number needs to know first whether the number deserves belief.

**What is distinctive.**

1. Trust comes before interpretation. Data quality and health status are separate answers, with
   separate vocabularies, in every output.
2. The reference is personal and specific to the mission phase. There are no population ranges
   anywhere in the system.
3. The system reasons over time and can decline to answer. `insufficient_data` is a first-class
   result, not an error.
4. Everything is explainable and reproducible. There is no trained model: each status comes with
   the rule, the records used and the settings, and the same input always gives the same output.

**What we do not claim.** No clinical validation, no diagnosis, no treatment advice, no real
astronaut data. The thresholds in the demonstration are demonstration settings.

## B. Ninety-second internal demonstration

For rehearsal and for the Local Event if a live pitch is allowed. Scene details and exact values
are in [primary-demo-flow.md](primary-demo-flow.md).

| Time | Screen | Action | Narration | Backend | Interface |
| --- | --- | --- | --- | --- | --- |
| 0:00-0:12 | Crew overview | Two crew cards, both with an amber data badge | "Far from Earth, an astronaut has to judge their own health data. Here are two crew members. Both have a data warning. The reasons could not be more different." | Implemented | Pending |
| 0:12-0:32 | Astronaut view, Scene A | Select the first crew member. Point to the marked night; open its note | "On night six the tracker reported minus thirty minutes of sleep. That is not a bad night, it is a bad measurement. OrbitVitals marks it unusable, says why, and keeps it out of the analysis. The remaining nights show no trend. Note the wording: no configured signal, not healthy." | Implemented, verified | Pending |
| 0:32-0:38 | Action Center | Open "What can I do?" | "A measurement problem gets a measurement fix: check the device, record again." | Not implemented | Pending, static text |
| 0:38-1:05 | Astronaut view, Scene B, with the time slider | Select the second crew member. Move the slider through 2, 5 and 9 nights | "Here nothing looks wrong. After two nights the system refuses to judge. After five it asks for review. After nine, recorded sleep has fallen about fifteen minutes a night, two hours in all, and it still tells me two nights are missing." | Implemented, verified | Pending |
| 1:05-1:15 | Evidence panel | Open "Why?" | "Every result explains itself: which nights were used, which rule fired, which settings applied." | Implemented | Pending |
| 1:15-1:23 | NASA Research Lens | Open "Why it matters" | "And why sleep matters in space, in NASA's own words, with what NASA does about it." | Content prepared | Pending, static content |
| 1:23-1:30 | Action Center | Press "Share with flight surgeon" | "The next step is a person. This is a screening prototype on simulated data, built to be checked." | Not implemented | Pending, client-side |

If the interface is not ready for a rehearsal, run the same story from the terminal with
`python -m app.scenarios replay sensor_quality_failure` and
`python -m app.scenarios replay progressive_sleep_restriction`. The checkpoint lines and PASS
markers tell the same story.

## C. Extended demonstration, three to five minutes

For internal rehearsal, mentors and technical discussion.

| Beat | Time | Content | Shown | State |
| --- | --- | --- | --- | --- |
| 1. The problem | 0:00-0:30 | The challenge sentence about astronauts spotting changes in themselves. Two ways a number misleads | Title, then crew overview | Narrative |
| 2. Three questions | 0:30-0:55 | Can I trust it? What is my reference in this phase? What changed? Then: what can I do? | The three lanes | Design implemented in the contract; interface pending |
| 3. Scene A | 0:55-1:45 | Seven nights, three faulty records. Per-record notes. Window quality `degraded`, evaluation `nominal`. Explain why `nominal` is not "healthy" | Astronaut view, Evidence panel | Backend verified |
| 4. Scene B | 1:45-3:00 | Nine nights, two missing. The slider: `insufficient_data`, then `attention`, then `attention` with more evidence. Read one line of the explanation aloud | Astronaut view, Decision Replay | Backend verified |
| 5. Reproducibility | 3:00-3:35 | Run `python -m app.scenarios replay all --validate` in a terminal. Expected-against-actual checks, all PASS, 765 contract payloads validated. State what tests do and do not prove | Terminal | Implemented and demonstrated |
| 6. NASA evidence | 3:35-4:05 | Research Lens for sleep: the NASA risk, NASA's description, what NASA does. State that no NASA dataset is computed on | Research Lens | Content prepared; interface pending |
| 7. The next step | 4:05-4:30 | Follow-up cards and the flight-surgeon summary. No prescription | Action Center | Not implemented; client-side proposal |
| 8. Limits and next | 4:30-5:00 | Simulated data; demonstration settings; no clinical validation; vital signs and cognition are prototypes. Next: device ranges, real data, validated policies | Closing slide | Narrative |

Optional inserts, 30 to 40 seconds each, only for a technical audience:

- **Personal reference by phase.** Replay `personalized_baseline`: pre-flight median 58 bpm from
  14 values, in-flight median 64 bpm from 12, launch `insufficient_data`, post-flight not
  available. Say "one reference per phase". The values are authored; do not call the difference
  an expected adaptation.
- **Exercise.** Replay `exercise_adherence_change`: decreasing runs, a rest day that is not a
  miss, an incompletely recorded week that stays `unknown`.

## D. Submission-compliant demo

Verified rules (Project Submission Guide, 2026): the demo is a "Video (30 seconds or less) or
slide deck (up to seven slides including title and intro slides)". "Projects that exceed these
limits will not be eligible for Global Judging." Slides must be in English and must address
"Team name", "Names of team members" and "The challenge your team selected". The link must be
public, with no login. The guide adds that "the majority of judges' evaluation will be based on
your project submission", so section D3 matters as much as the demo.

**Recommendation: submit the seven-slide deck.** Our idea needs one diagram and one explicit
statement about NASA resources, which thirty seconds can barely hold. Slides also depend only on
screenshots, not on a flawless live run. Prepare the video script as well, and choose on Sunday
afternoon: if the interface is polished and the story lands in a timed recording, the video is
the more striking option. Only one link goes in the demo field.

### D1. Thirty-second video

Follows the time-coded structure suggested by the Submission Guide. About 80 spoken words, which
is brisk; record against a stopwatch and cut the last sentence if it runs over. The export must
be 30.0 seconds or less, titles included.

| Time | Picture | Narration | On-screen text |
| --- | --- | --- | --- |
| 0:00-0:02 | Title card | "We're team [team name]." | Team name, member names, challenge title |
| 0:02-0:05 | Crew overview | "Far from Earth, astronauts must judge their own health." | |
| 0:05-0:10 | The three lanes | "OrbitVitals AI: know what to trust, what changed, and what to do next." | Tagline |
| 0:10-0:15 | Scene A: the marked night and its note | "Minus thirty minutes of sleep? A faulty reading, not a health problem." | "Data problem, not a health finding" |
| 0:15-0:21 | Scene B: slider from 2 to 9 nights, then the Research Lens | "Sleep slipping fifteen minutes a night? A real trend, explained, with NASA research one tap away." | "Informed by NASA Human Research Program resources" |
| 0:21-0:30 | Action Center, then closing card | "Each result shows how far to trust it and when to involve the flight surgeon. Open source and reproducible, on simulated data. A step toward self-reliant crews." | Repository link |

Requirements to check before upload:

- A caption "Simulated data. Research prototype, not a medical device." visible throughout.
- Spoken English, or English subtitles if another language is spoken.
- No NASA logo or insignia in any generated graphic.
- If any image, video or voice was generated with an SI tool, add the visible watermark or the
  acknowledgement the rules require.
- No person under 18 appears or is heard.

### D2. Seven-slide deck

Keep each slide to one idea and about 25 words of body text. Static screenshots only; an embedded
video could be read as a way around the 30-second limit.

| No. | Slide | Visual | Text on the slide |
| --- | --- | --- | --- |
| 1 | Title | Product name over a screenshot of the astronaut view | "OrbitVitals AI. Know what to trust, what changed, and what to do next." Team name. Names of team members. Challenge: "Create Health Monitoring Software for Astronauts on Space Missions" |
| 2 | The problem | Two small charts side by side: one with an absurd spike, one with a gentle slope | NASA: "astronauts carry much of the responsibility for spotting these changes in themselves." A number can mislead twice: a faulty reading looks alarming; a slow change looks fine |
| 3 | The idea | Diagram of three lanes leading to an action | Can I trust it? What is my own reference in this mission phase? What changed over time? Then: what can I do? Each answer is separate, explained, and allowed to be "not enough data" |
| 4 | Scene A | Screenshot: marked night, quality note, `nominal` with amber data badge | "-30 minutes of sleep." Flagged as a faulty record with the reason. Kept out of the analysis. No health conclusion drawn |
| 5 | Scene B | Screenshot: slider at 2, 5 and 9 nights | Nothing looks wrong. 2 nights: not enough data. 5 nights: review suggested. 9 nights: sleep down about 15 min a night; 2 nights still missing |
| 6 | NASA resources and science | Table: indicator, NASA risk, what we do | Indicators chosen from NASA Human Research Program risks, shown in the product. Methods from NIST references. All crew data is simulated. 729 automated tests verify the software, not clinical validity |
| 7 | Next step and outlook | Screenshot of the Action Center; repository link | Every finding ends with a next step and a summary for the flight surgeon. Open source, reproducible with one command. Next: real device ranges, real data, validated settings |

Slide 6 should say in so many words that no NASA dataset is computed on. A judge who discovers
that alone will trust the rest less than one who is told.

### D3. Project page field drafts

Starting points for the team to edit. Square brackets mark what only the team can supply. Check
every statement against the product as it actually stands at submission time.

**Project Name.** OrbitVitals AI

**High-Level Project Summary.**

> OrbitVitals AI is an explainable health-monitoring prototype for astronauts on long missions.
> It addresses a problem that grows with distance from Earth: a crew member who must judge a
> reading alone first needs to know whether to believe it. For each indicator the tool answers
> three separate questions: can this measurement be trusted, what is this person's own
> reference in the current mission phase, and has something changed over time. It explains every
> answer in words, says "not enough data" when that is the truth, and ends with a next step,
> including a summary to share with the flight surgeon. We demonstrate it on simulated sleep
> data: a faulty reading is identified as a measurement problem, while a slow decline that no
> single night reveals is flagged for review. It is a research prototype, not a medical device.

**Detailed Project Description.** Suggested structure:

> **What it does.** Gathers health indicators, checks each record's quality, builds a personal
> reference for each mission phase, screens sleep and physical activity for changes over time,
> and presents the result in three separate lanes with a written explanation and a next step.
>
> **How it works.** A Python 3.11 backend with a FastAPI interface runs four deterministic
> engines. The Data Quality Engine flags records that are provably wrong (impossible values,
> duplicates, a diastolic pressure above the systolic one) and reports missing observations.
> The Personal Baseline Engine computes reference statistics per crew member, metric and mission
> phase, screening potential outliers with the modified z-score. The sleep module fits a
> Theil-Sen slope through the recorded nights and reports a trend only when explicit settings
> are met. The activity module compares recorded exercise with a personal plan. [Describe the
> interface as built.]
>
> **What is real today.** [Adjust to the final state.] The four engines and the API are
> implemented and covered by 729 automated tests. Five reproducible scenarios replay with one
> command. Blood-pressure, temperature and cognition modules exist as early prototypes and are
> not part of the demonstration.
>
> **Benefits.** Fewer false alarms from bad data, earlier attention to slow changes, and results
> a crew member can check for themselves.
>
> **Limitations.** All crew data is simulated. Detection settings are demonstration values, not
> clinical thresholds. Nothing has been validated against real astronaut data. The tool does not
> diagnose or prescribe.
>
> **Tools.** Python, FastAPI, Pydantic, pytest, Ruff; [frontend stack]; [SI tools, see below].

**Use of Super Intelligence (SI).** The rules require a description, and for code and data an
acknowledgement "in descriptive text and metadata". Draft, to be completed truthfully:

> We used SI coding assistants ([list every tool actually used, for example Claude Code and
> Codex]) to help write, test and document the backend, to draft documentation, and to help
> check our scientific references against their sources. The idea, the scope and the scientific
> rules of the project (no invented thresholds, every constant sourced, synthetic data always
> labelled) were set by the team, and team members reviewed the generated work. The simulated
> datasets are hand-specified fixtures. [State whether any image, video, audio or interface
> asset was generated with SI tools, and where the watermark or acknowledgement appears.]

Also add a short "Use of SI tools" section to the root README so that the acknowledgement is in
the repository itself. The rules say SI "should not be used to (come up with your idea of how to
solve the challenge)"; describe the team's own contribution accurately.

**NASA Data.** The form says: "To be eligible for a Global Award, you must use at least one NASA
data or resource." Draft:

> We used NASA Human Research Program resources to decide which indicators to monitor and to
> explain each of them inside the product: "5 Hazards of Human Spaceflight" and "Risks of Human
> Spaceflight", in particular the pages on inadequate sleep and irregular schedules, reduced
> cardiorespiratory and musculoskeletal fitness, cardiovascular adaptations, and behavioral
> changes. NASA's OCHMO-TB-031 Exercise Overview, which cites NASA-STD-3001 requirements written
> relative to each crew member's own baseline, motivated our personal-reference design. These
> resources appear in the tool's NASA Research Lens next to each finding. We did not use a NASA
> dataset: every measurement in the demonstration is simulated and labelled as such.

**Space Agency Partner Data and Other References.** Use the list in
[scientific-evidence-matrix.md, section 7](scientific-evidence-matrix.md#7-reference-list), plus
all software dependencies and any images, icons and fonts. No Space Agency Partner resource is
used at present; do not list one unless it is.

**Links.** Open the demo link and the final-project link in a private browser window before
submitting. The guide allows editing and resubmitting until the deadline, and "only your last
saved submission will be reviewed". Submit a complete early version on Sunday afternoon and
improve it afterwards.

## E. The science in plain language

Accurate enough for a specialist, short enough to say aloud.

**Data Quality Engine.** Before anything is interpreted, each record is checked for errors that
can be proven from the data: a negative duration, a percentage above 100, a sleep duration longer
than its recording interval, a diastolic pressure above the systolic one, a duplicate, a
timestamp in the future. A window of records is then described by how many expected observations
are present and usable. The engine never judges a value for being high or low; that is a health
question. Today it has no device measuring ranges and cannot detect drift.

**Personal Baseline Engine.** For each crew member, metric and mission phase it computes the
mean, standard deviation, median, median absolute deviation, minimum and maximum of the
trustworthy values. Unusual reference values are pointed out with the modified z-score from the
NIST handbook, `0.6745 × (value − median) / MAD`, with the published cut-off of 3.5, and are
kept by default. A baseline is `insufficient_data`, `provisional` or `established`. It becomes
`established` only when criteria supplied by the mission team are met; the engine has no default
criteria, because we have no source for them.

**Sleep trend screen.** The module takes one sleep summary per night and fits a Theil-Sen slope:
the median of the slopes between every pair of recorded nights, using real elapsed time, so a gap
of two days is not treated as one step. It reports a progressive reduction only if there are
enough nights, enough coverage, a steep enough slope, a large enough fitted change and a
consistent direction. All of these are explicit settings; the demonstration uses labelled
demonstration values. It is a screen that requests human review. It is not a significance test
and it does not estimate sleep debt.

**Physical activity review.** Recorded exercise minutes and active energy are summed per day and
week and compared with the crew member's own plan and, when available, their own baseline. A run
of strictly decreasing days is reported as a reduction. A day counts only if the recording was
confirmed complete; otherwise the result is `unknown`. Planned rest is never a missed target.

**What the statuses mean.** `attention`: a configured rule was met with sufficient data; a
person should look. `nominal`: enough data and no configured signal; this does not establish
health. `insufficient_data`: the system cannot tell. `alert` is never produced, because no
validated basis for an emergency level exists in this prototype.

**Why it is reproducible.** No randomness, no trained model, no hidden state. Assessment times
are inputs, identifiers are derived from content, and the five scenarios compare expected with
actual outputs each time they are replayed.

**Not in the demonstrated pipeline.** Early prototypes for blood pressure and temperature
(pre-flight reference shifted by group changes published for ISS crews) and for cognitive test
scoring (against published pre-flight norms of 25 astronauts) exist in the repository. They are
untested and not integrated. Their evidence and open issues are items E11 to E15 of the
[evidence matrix](scientific-evidence-matrix.md).
