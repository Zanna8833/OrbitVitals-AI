# NASA challenge alignment

Official 2026 requirements, verified against the NASA Space Apps Challenge website, and an
honest assessment of how OrbitVitals AI meets each of them.

Repository state assessed: commit `667f512` on `feature/demo-storyboard` (2026-11-14).
Nothing in this document is a claim of clinical validity. OrbitVitals AI is a research
prototype, not a medical device.

## 1. Sources and how they were verified

Every page below was retrieved directly from the official site on 2026-11-14. Text in quotation
marks is verbatim.

| Source | URL | Used for |
| --- | --- | --- |
| Challenge statement | <https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/> | Problem, objectives, optional considerations |
| Challenge resources tab | <https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/?tab=resources> | NASA and partner resources |
| Judging & Awards Guide | <https://www.spaceappschallenge.org/resources/judging-awards-guide/> | Eligibility, judging criteria, awards, dates |
| Project Submission Guide | <https://www.spaceappschallenge.org/resources/project-submission-guide/> | Form fields, demo limits, deadline, SI disclosure |
| Participant FAQs | <https://www.spaceappschallenge.org/resources/participant-faqs/> | Dates, team rules, pre-event work, SI definition |
| Participant Terms and Conditions | <https://www.spaceappschallenge.org/legal/> | Licensing, third-party materials, citation |

Verification limits:

- The Terms and Conditions were searched by keyword (licensing, third-party materials, citation,
  originality). They were not read end to end. Read them in full before ticking the box.
- Rules of the team's **Local Event** (local pitch format, local judging time, local awards) were
  not verified: this repository does not record which Local Event the team joined. The Judging
  Guide says to contact the Local Lead about local deadlines.
- The challenge page metadata shows it was last published on 2026-11-13, and it says "More
  resources may be added before the hackathon begins." Re-check the Resources tab once before
  submitting.

## 2. The challenge in NASA's words

**Title:** "Create Health Monitoring Software for Astronauts on Space Missions".
Difficulty: Intermediate. Skills: Human Exploration, Software, Space Exploration.

**Summary:** "On long missions, astronauts carry much of the responsibility for spotting these
changes in themselves. Your challenge is to build a health monitoring software that gathers
health indicators and enables astronauts to evaluate and act on the status of their health."

**Objective:** "Your challenge is to create a visual tool that helps astronauts assess their own
health during space missions and provides guidance on treatments and health improvements."

**Indicators named as useful:** "blood pressure, heart rate, blood sugar, body temperature, daily
sleep hours, and mood."

**Questions the statement asks teams to consider:**

1. "Which measurements can be performed in space?"
2. "Why is an exam needed?"
3. "How do spaceflight hazards affect these health indicators?"
4. "When might a result warrant attention from the crew or from flight surgeons on the ground?"
5. "What actions can be taken to prevent a critical health condition?"

**On the interface:** "User interface design plays an important role in presenting metrics and
diagnosis clearly. You may consider taking advantage of animations and interactivity to present
the information."

**Official resources for this challenge:**

- NASA: [5 Hazards of Human Spaceflight](https://www.nasa.gov/hrp/hazards/),
  [Risks of Human Spaceflight](https://www.nasa.gov/hrp/risks/),
  [Ongoing HRP Research in Space](https://www.nasa.gov/hrp/ongoing-hrp-research/).
- CSA: [Monitoring Radiation for Astronaut Health](https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp),
  [Why Do We Conduct Science Experiments in Space?](https://www.asc-csa.gc.ca/eng/iss/science/why-do-we-conduct-science-experiments-in-space.asp).

The official NASA resources for this challenge are explanatory pages, not downloadable datasets.

Three consequences for our project follow directly from this wording:

- **The primary user is the astronaut**, assessing their own health. Ground medical staff are
  the escalation path, not the main audience.
- **A visual tool is the deliverable.** A backend without an interface does not answer the
  objective.
- **The tool is expected to help the astronaut act**, not only to display a status.

## 3. Mandatory requirements, judged criteria and suggestions

### 3.1 Mandatory for eligibility and submission

Source: Judging & Awards Guide ("Minimum requirements") and Project Submission Guide, unless
noted. "Team to confirm" marks administrative items that cannot be checked from the repository.

| ID | Requirement (official wording, shortened) | Status |
| --- | --- | --- |
| M1 | "Respond to one of the official NASA Space Apps Challenges." | Met: the project addresses the challenge in section 2 |
| M2 | All members registered for the same Local Event (not waitlisted) and listed on the team page; at most six members | Team to confirm |
| M3 | "Complete all of the required fields on the Project Submission page." | Pending; drafts in [presentation-storyboards.md](presentation-storyboards.md) |
| M4 | Demo as "a slide presentation (7-slide limit including title and intro slides) or a video presentation (30-second limit)" | Pending; see M4 note below |
| M5 | "Use English language on the project submission page and in any linked materials." A video may be spoken in another language only with English subtitles | Repository is in English. Check interface text, slides and video |
| M6 | Submit "before Sunday, November 15 at 11:59 p.m. local time in accordance with your team's Local Event" | Pending |
| M7 | Tick the Terms and Conditions box and the original-work box: "all external resources including code, text and images (even if they are open source or freely available) used in the project are listed in the References field" | Pending; reference list in [scientific-evidence-matrix.md](scientific-evidence-matrix.md#7-reference-list) |
| M8 | Review for prohibited bilateral activity with China or a Chinese-owned entity | Team to confirm |
| M9 | NASA Data field: "To be eligible for a Global Award, you must use at least one NASA data or resource." | Met in substance (NASA resources inform the design). Must be stated in the form and should be visible in the product |
| M10 | "Use of Super Intelligence (SI)": describe how SI tools were used. "Code and data: Must acknowledge SI generation in descriptive text and metadata." Images and videos generated with SI need "a visible watermark" | Pending; draft in [presentation-storyboards.md](presentation-storyboards.md#d3-project-page-field-drafts) |
| M11 | Demo and final-project links must be "publicly accessible", requiring no "password, permission, or registration" | Pending; test every link in a private browser window |
| M12 | Original content must be freely available or under an OSI-approved open-source licence (Terms) | Met: [LICENSE](../../LICENSE) is Apache-2.0 |
| M13 | "You must cite every source that is used in the creation of your project, even if it is open source or freely available." (Terms) | Pending; see M7 |
| M14 | "Teams are not allowed to begin working on the challenges prior to the hackathon." (FAQ) | Met: every commit is dated 2026-11-14; the first at 11:07 +01:00 (`git log`) |
| M15 | No image, video, audio or likeness of persons under 18 in the demo or project | Team to confirm |
| M16 | "Generated content may not use, contain, or modify any NASA branding or design elements (such as the NASA logos, flags, or mission identifiers)." | Check slides, video and interface |

**M4 note. The 30-second and seven-slide limits are confirmed for 2026.** The Submission Guide
states: "Limitations: Adhere to the 30-second and 7-slide limits. Projects that exceed these
limits will not be eligible for Global Judging." It also sets what slides must contain: "Team
name", "Names of team members", "The challenge your team selected". The same guide adds an
important weighting: "This demo will be considered in your overall project evaluation, but the
majority of judges' evaluation will be based on your project submission." The written project
page therefore deserves as much care as the demo.

Terminology: the 2026 materials use "Super Intelligence (SI)" where earlier years said AI. No
rule was found on the pages consulted that restricts the word "AI" in a project name. Answer the
SI question under that heading in the form.

### 3.2 Judging criteria

Each criterion is scored from 1 to 5 "at every level of judging". Key phrases:

| Criterion | What judges look for (verbatim excerpts) |
| --- | --- |
| Impact | "addressing either a minor or major problem"; "The extent to which it inspires or helps others" |
| Creativity | "originality and innovation"; "an improvement upon existing ideas in a meaningful way" |
| Validity | "grounded in scientific principles and demonstrates technical, functional, or logical feasibility"; "usability and user-friendliness" |
| Relevance | "fully and directly addresses the challenge"; "meaningfully integrates NASA data, utilizing it as a core component of the proposed solution rather than a superficial addition" |
| Presentation | "clearly conveying the challenge, their proposed solution, and its significance"; "Judges evaluate the demo and full project to compute this score." |

### 3.3 Optional suggestions

The statement introduces these with "You may (but are not required to) consider": other
environments (spacecraft, station, rover, surface base); prompting astronauts to take
measurements; gamification; dynamic charts of indicators over time; colour coding; and "simple
instructions and explanations covering measurements, health indicators, and risks", because
teams should "not assume that astronauts know everything about how to assess their health".

### 3.4 Our own interpretations (not NASA requirements)

- Separating data trust, personal reference and physiological change is our design choice. The
  challenge does not ask for it; it is our answer to "enables astronauts to evaluate".
- Withholding diagnoses and prescriptions is our scientific-integrity rule (see
  [AGENTS.md](../../AGENTS.md)). The challenge itself uses the words "diagnosis" and
  "treatments", so judges may ask why we stop short. See
  [judge-questions.md](judge-questions.md).
- Synthetic data is acceptable under the statement ("Any kind of data can be used, as long as it
  represents a health indicator"), but that sentence is about indicator types. It does not
  replace the NASA data expectation in the Relevance criterion.

## 4. Capability compliance matrix

Status scale: **Implemented and demonstrated**, **Implemented but not yet demonstrated**,
**Partially implemented**, **Planned**, **Unsupported or missing**. "Demonstrated" means a
runnable, reproducible demonstration exists in this repository.

| ID | Official expectation | Status | Evidence in the repository | What is missing |
| --- | --- | --- | --- | --- |
| C1 | "gathers health indicators" | Partially implemented | `POST /measurements` accepts 15 catalogued metrics and assesses each record (verified over HTTP on 2026-11-14) | An astronaut-facing way to enter or import values. No interface code is in the repository |
| C2 | "enables astronauts to evaluate ... the status of their health" | Partially implemented | Sleep and physical-activity evaluation run end to end (replay and HTTP). Personal baselines work for any metric | Blood pressure and temperature evaluation exists only as an unintegrated, untested prototype. No heart-rate, blood-sugar or mood evaluation |
| C3 | "act on the status of their health"; "provides guidance on treatments and health improvements" | Unsupported or missing | Outputs say that a person should review the records. No next step is produced by the API | Follow-up guidance. Proposed as cited, non-prescriptive cards in [frontend-demo-mapping.md](frontend-demo-mapping.md#6-follow-up-actions) |
| C4 | "create a visual tool" | Planned | `frontend/` holds only a placeholder README | The whole interface. Its real status could not be verified from this repository |
| C5 | Use HRP resources "to understand how spaceflight hazards affect human health, and to decide which indicators are useful" | Partially implemented | NASA OCHMO-TB-031 is cited in [physical-activity-monitoring.md](../physical-activity-monitoring.md); spaceflight studies are cited in `vitals.py` and `cognition.py` | Nothing is visible to the user. Hazard-to-indicator mapping is prepared in [scientific-evidence-matrix.md](scientific-evidence-matrix.md#4-nasa-hazards-and-risks-behind-each-indicator) |
| C6 | "Which measurements can be performed in space?" | Partially implemented | Metric catalogue with canonical units (`GET /metrics`) | A sourced rationale per measurement |
| C7 | "Why is an exam needed?" | Planned | None in the product | Short cited explanations (NASA Research Lens content) |
| C8 | "How do spaceflight hazards affect these health indicators?" | Planned | Mapping prepared in this package only | Display in the product |
| C9 | "When might a result warrant attention from the crew or from flight surgeons on the ground?" | Implemented and demonstrated | The `attention` status with a written explanation, for sleep trends and activity (five replay scenarios, 729 passing tests, HTTP run) | Visual presentation |
| C10 | "What actions can be taken to prevent a critical health condition?" | Unsupported or missing | None | Same gap as C3 |
| C11 | "presenting metrics and diagnosis clearly" | Planned | Explanations exist as text, written for engineers | A plain-language layer and the interface |
| C12 | Optional: prompts to take measurements | Partially implemented | Missing nights and incomplete recordings are identified by date in the outputs | A prompt in the interface |
| C13 | Optional: dynamic charts over time | Planned | Time series available from `GET /crew-members/{id}/measurements` | Charts |
| C14 | Optional: colour coding | Planned | Three separate status vocabularies exist in the contract | Visual encoding |
| C15 | Optional: simple instructions and explanations | Partially implemented | Every finding carries an `explanation` | The wording is technical (for example "Theil-Sen slope") |
| C16 | Optional: several environments | Unsupported or missing | Mission phases only | Not recommended before the deadline |
| C17 | Optional: gamification | Unsupported or missing | None | Not recommended before the deadline |

## 5. Judging criteria: where we stand

| Criterion | Current strength | Why | What raises it before submission |
| --- | --- | --- | --- |
| Impact | Moderate | The problem is real and named by NASA: astronauts must judge their own health far from help. Our contribution is credibility of the signal, which is hard to see without an interface | Show the two-scene contrast in [primary-demo-flow.md](primary-demo-flow.md) and one clear next step per finding |
| Creativity | Strong | Most monitoring dashboards go straight from a number to a colour. We keep "can I trust it", "what is my reference" and "what changed" apart, and the system is allowed to answer "not enough data" | Make the three lanes the visual signature of the interface |
| Validity | Strong on engineering, cautious on science | Deterministic engines, sourced formulas, 729 tests, reproducible replay. No clinical validation, and every threshold in the demonstration is a labelled demonstration setting | Say exactly this. Do not present the unintegrated vitals and cognition code as working features |
| Relevance | **Weakest** | The challenge is addressed directly, but no NASA dataset enters any computation shown in the demonstration. NASA material is used as cited research and context | Make NASA HRP content a visible, structural part of every finding, list each resource precisely in the NASA Data field, and state the limit openly |
| Presentation | Not yet determined | Depends on the interface, the demo and the project page, none of which exist in the repository yet | Follow [presentation-storyboards.md](presentation-storyboards.md); rehearse to the limits |

## 6. Genuine competition risks

Ranked by likelihood and consequence. All are evidenced above; none is speculative.

1. **No verified visual tool.** The challenge asks for one. The repository contains no interface
   code, and the documentation still names Flutter while the team is building in React.
2. **Relevance and NASA data.** A judge applying the rubric literally will look for NASA data as
   "a core component". We have NASA resources and literature, plus synthetic measurements.
3. **Actionability gap.** The statement asks for "guidance on treatments and health
   improvements". Today the system ends at "review suggested".
4. **Ground-operator framing.** Screen names such as Mission Control suggest a tool for flight
   controllers. The challenge is about astronaut self-assessment.
5. **Demo limits.** Our reasoning chain is hard to compress. Exceeding 30 seconds or seven slides
   removes eligibility for Global Judging.
6. **Overclaiming.** Calling anything validated, citing the test count as scientific evidence, or
   presenting the vitals and cognition prototypes as features would damage the Validity score if
   a judge opens the repository.
7. **Incomplete SI disclosure.** The project was built with substantial help from coding
   assistants. The rules require this to be described, and judges "will evaluate originality,
   intent, and execution based on the SI-assisted elements you include and identify".
8. **The repository front page.** The final-project link will probably be the repository. Its
   root README still says the algorithms are "not implemented yet" and describes a Flutter
   client.
9. **Demo fragility.** Storage is in memory. A server restart or auto-reload erases all data.
10. **Breadth of indicators.** Of the six indicators the statement names, only sleep is fully
    evaluated. This is acceptable if presented as depth over breadth.

Mitigations and owners are in [prioritized-gaps.md](prioritized-gaps.md).

## 7. Open uncertainties

- Whether the Local Event adds a live pitch with its own time limit.
- Whether a longer walkthrough video may be linked from the project page in addition to the
  compliant demo. The limit is written for the demo field. To stay safe, keep the demo link
  strictly within the limit and ask the Local Lead before linking anything longer.
- Whether the repository is publicly readable without signing in. Check in a private window.
- The real state of the React interface, which is outside this repository.
