# Project description drafts

These copy blocks describe the assessed implementation. Before publication, update
the interface sentence only after Demo 6 passes acceptance, complete the public
links in the submission form and confirm the live form's field limits.

## Project name

OrbitVitals AI

## One-line description

Explainable physiological monitoring that separates data quality, personal
references and longitudinal change for human review during space missions.

## High-level project summary

OrbitVitals AI is a research prototype for helping astronauts review physiological
changes over time. Its backend separates three questions: can a measurement be
used, what is this person's reference, and has a configured pattern appeared?
It checks data quality, builds personal references by mission phase, and evaluates
sleep and physical activity using transparent statistical methods. In a reproducible
simulation, Noor's recorded sleep progressively shortens; the system initially
reports insufficient evidence and later suggests review, while retaining missing
nights and explaining the result. NASA Human Research Program resources provide
the spaceflight context. All demonstrated observations are synthetic. The scientific
API and bridge are implemented; final integration with Silvio's approved Demo 6
interface is pending. Outputs support human oversight, not diagnosis or treatment.

## Executive summary

Health monitoring needs to make uncertainty visible as well as change. A corrupted
sensor record, a limited personal history and a sustained physiological pattern
are different problems. OrbitVitals AI keeps them separate.

The prototype's Data Quality Engine assesses observations before interpretation.
Its Personal Baseline Engine describes each crew member's usable reference history
within a mission phase. Sleep and physical activity modules then evaluate explicit
observation windows using documented statistical policies. Each stored result
includes explanations and algorithm identity. Missing information can produce
`insufficient_data` rather than an invented conclusion.

The strongest demonstrated case is Crew B / Noor: seven recorded nights within a
nine-night window show progressively shorter sleep. The selected personal median
reference is 480 minutes; the evaluated median is 430 minutes. The trend screen
reports -15 minutes per day. Two missing nights remain visible. A two-night replay
does not support a trend conclusion; later checkpoints suggest review.

NASA resources motivate the monitoring priorities; NASA participant records do not
enter this demonstration. Its measurements and screening settings are simulated.
Software tests establish reproducible behavior, not medical accuracy. The approved
visual interface is Silvio's Demo 6; the matching React integration remains pending.

## Detailed project description

### Problem

Long-duration missions require crew members to review changes in their own health
indicators. NASA identifies sleep disruption and other human-system risks in the
spaceflight environment. A display of isolated measurements cannot by itself
explain whether a record is usable, whether a personal comparison is available,
or whether a change persists across time. Missing and corrupted observations add
uncertainty that should remain visible. [NASA sleep-risk resource](https://www.nasa.gov/reference/risk-from-inadequate-sleep-and-irregular-schedules/)

### Proposed solution

OrbitVitals AI organizes monitoring around data trust, personal reference and
longitudinal change. The backend accepts canonical measurements through FastAPI,
assesses their quality, computes eligible personal baselines and stores sleep or
activity evaluations. The TypeScript bridge validates response contracts and
exposes the actual observations, reference statistics, findings and explanations.
The final interface will use Silvio's approved Demo 6 design, with honest unavailable
states where a measurement, evaluation or backend operation does not exist.

### What is implemented and demonstrated

The Data Quality and Personal Baseline engines, sleep trend analysis, physical
activity monitoring, five deterministic scenarios, mission seeder and HTTP bridge
are implemented. An isolated run stores 498 synthetic measurements, 21 baselines
and 13 evaluations for three synthetic crew members. The Noor replay demonstrates
progressive sleep restriction, personal comparison, recording gaps and an initial
refusal to conclude from insufficient evidence.

The API returns the scientific engines' actual outputs. It does not simulate
statuses. The recorded sleep median is 50 minutes below Noor's selected personal
median; the trend, rather than the configured absolute-deviation criterion, is
what prompts review in this example. No diagnostic or emergency label is inferred.

### Scientific innovation

The contribution is the combination of explainable, uncertainty-aware monitoring
steps in a reproducible workflow. Quality assessments describe observations;
baseline maturity describes the reference; evaluation status describes the outcome
of a configured screen. The system preserves those distinctions and records why
a result was reached. Its statistical methods are established techniques, not a
newly validated medical model.

### NASA use

NASA Human Research Program hazards and risk resources inform the problem framing,
the choice to demonstrate sleep and exercise monitoring, and the scientific context
provided in this submission. They do not supply the numerical values or thresholds
in the replay. No NASA observational dataset is ingested by the assessed pipeline.
A separate NASA data workstream requires its own provenance and integration review
before any broader claim is added. [Resource ledger](nasa-provenance-and-references.md)

### Benefits and intended next step

The intended benefit is to make monitoring results easier to inspect and discuss:
review the observations, understand their limitations, and consult a flight surgeon
with the evidence. This is a design objective, not a measured improvement in health,
performance, false alarms or clinical outcomes. HTTP messaging and treatment guidance
are not implemented. A recommended human review does not claim that the application
has sent a report or selected a treatment.

### Implementation and limits

The assessed stack is Python 3.11, FastAPI, Pydantic contracts and JSON Schema,
deterministic Python statistical modules, a TypeScript bridge, and React/TypeScript.
Storage is in memory. All crew observations are simulated, and demonstration
policies are not clinical thresholds. There is no validation against real astronaut
data, no demonstrated runtime language-model reasoning and no completed Demo 6
HTTP visual acceptance. MedGemma 1.5 is a separate workstream pending confirmation.

## NASA resource field

We used NASA Human Research Program resources on human-spaceflight hazards and
risks, particularly inadequate sleep and irregular schedules and reduced physical
fitness, to frame the monitoring problem and select the demonstration domains.
These resources provide scientific context for the submission. NASA observational
data do not enter the assessed computations: every crew measurement is explicitly
simulated, and the screening settings are demonstration choices. We do not claim
that NASA validated the algorithms, set their thresholds or endorsed the project.
The separate NASA data pipeline is not included in these demonstrated-use claims.

## Publication conditions

- Replace no unknown field with an invented team, event or project URL.
- Keep the interface integration caveat until the actual matching implementation
  passes the [acceptance specification](demo6-acceptance.feature).
- Use the [AI disclosure and contributor credits](ai-tools-and-credits.md).
- Keep NASA resource context separate from numerical dataset use and from future AI.
- Do not claim reduced medical risk, sleep-debt prediction, diagnostic sensitivity,
  fewer false alarms or autonomous treatment without new evidence.
