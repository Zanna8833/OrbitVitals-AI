# Prioritized gaps

What still stands between the current repository and a coherent, compliant submission, ranked
for a three-person team with about a day left.

Assessed at commit `667f512` on 2026-11-14 (Saturday afternoon, local time). The submission
closes on **Sunday, November 15 at 11:59 p.m. local time**.

## 1. How gaps are ranked

Each gap is rated High, Medium or Low on six dimensions.

| Dimension | Question |
| --- | --- |
| NASA relevance | Does the official challenge text or the judging rubric ask for it? |
| Judge understanding | Without it, will a judge miss what the project does? |
| Scientific importance | Does it affect the credibility of a claim we make? |
| Effort | Small: under 2 hours. Medium: 2 to 5 hours. Large: more |
| Dependency | Who or what must deliver first |
| Distraction risk | How likely it is to pull time away from the core demonstration |

Classes: **P0** essential before submission; **P1** high value if feasible; **P2** optional or
after the hackathon.

## 2. Summary

| ID | Gap | Class | NASA relevance | Judge understanding | Scientific importance | Effort | Depends on | Distraction risk | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G1 | No verified visual tool for the primary flow | P0 | High | High | Medium | Large | G2 | None: this is the core | Silvio |
| G2 | Crew selection and data loading: seeded data, three sleep checkpoints, start procedure | P0 | Medium | High | Low | Small to Medium | Seeder and sleep HTTP work on other branches | Low | Andrea |
| G3 | NASA evidence is invisible in the product and unstated in the form | P0 | High | High | High | Small | Content is in this package | Low | Andrea, then Silvio |
| G4 | No astronaut-facing follow-up action | P0 | High | High | Medium | Small to Medium | G1 | Low | Silvio |
| G5 | Explanations are written for engineers | P0 | Medium | High | Medium | Small | G1 | Low | Silvio |
| G6 | Submission package incomplete: project page, demo, links, SI disclosure, references, repository front page | P0 | High (mandatory) | High | Medium | Medium | G1 for screenshots | Low | Andrea, all |
| G7 | Claim discipline: prototypes, simulated data, wording | P0 | Medium | Medium | High | None | Nobody | None | Marco, all |
| G8 | Demonstration reliability: in-memory data, no backup | P0 | Low | High | Low | Small | G1, G2 | Low | Andrea, Silvio |
| G9 | Data provenance not shown: source, algorithm, version, settings | P1 | Medium | Medium | High | Small | G1 | Low | Silvio |
| G10 | Mission phase context not shown | P1 | Medium | Medium | Medium | Small | G1 | Low | Silvio |
| G11 | No personal reference inside the sleep flow | P1 | Medium | Medium | High | Medium | G2 | Medium | Andrea |
| G12 | Scientific issues in the vital-signs prototype comments | P1 | Low | Low | High | Small | Nobody | Low | Marco |
| G13 | Vital-signs evaluation not integrated (blood pressure, temperature) | P1, conditional | High | Medium | High | Large | G12; an API change | **High** | Marco, Andrea |
| G14 | Live "complete the record" interaction | P1, optional | Medium | Medium | Low | Medium | G1, G2 | Medium | Silvio, Andrea |
| G15 | No real NASA or partner dataset in any computation | P2 | High | Medium | High | Large | A suitable open dataset | **High** | After the hackathon |
| G16 | No scientific validation: false-positive behaviour, device ranges, reviewed settings | P2 | Medium | Low | High | Large | Real data | High | After the hackathon |
| G17 | Cognition scoring not integrated or tested | P2 | Medium | Low | High | Large | Test interface; equivalence check | High | After the hackathon |
| G18 | Missing API resources: crew list, mission timeline, structured trend fields, durable storage | P2 | Low | Low | Low | Medium to Large | Contract change by the whole team | Medium | After the hackathon |
| G19 | RAG evidence assistant, nutrition, other environments, gamification, body figure | P2 | Low | Low | Low | Large | Many | High | After the hackathon |

## 3. P0: essential before submission

### G1. A visual tool for the primary flow

The challenge objective is "to create a visual tool". No interface code is in the repository.
Done means: the astronaut view with three lanes and a chart, Scene A and Scene B selectable, and
the time slider for Scene B, reading from the running backend or from the replay fixture.
Specification: [frontend-demo-mapping.md](frontend-demo-mapping.md). Build the astronaut view
first; everything else hangs off it.

### G2. Crew selection and data loading

The interface needs something to read. Done means: one command starts the backend with the
sampling interval configured; one command seeds two simulated crew members (Scene A and Scene B)
and stores the three sleep evaluations for Scene B; identifiers are agreed with Silvio. The
seeder and the sleep HTTP demonstration are being built on other branches and were not reviewed
here. The requirements the demonstration places on them are in
[primary-demo-flow.md](primary-demo-flow.md#8-reproducing-the-outputs). Fallback with no
dependency: capture the replay output to a file and load it in the frontend.

### G3. NASA evidence in the product and in the form

The Relevance criterion asks for NASA data as "a core component", and the form states that a
Global Award requires "at least one NASA data or resource". Done means: the NASA Research Lens
panel shows the prepared NASA content next to each finding, and the NASA Data field lists the
resources and says plainly that no NASA dataset is computed on. Content:
[scientific-evidence-matrix.md, section 4](scientific-evidence-matrix.md#4-nasa-hazards-and-risks-behind-each-indicator).
Draft field text: [presentation-storyboards.md, D3](presentation-storyboards.md#d3-project-page-field-drafts).

### G4. Follow-up actions

The challenge asks that astronauts "act on the status of their health" and for "guidance on
treatments and health improvements". The backend ends at "review suggested". Done means: static
follow-up cards chosen by the kind of finding, and a "Share with flight surgeon" summary built
in the browser. No backend work. Specification:
[frontend-demo-mapping.md, section 6](frontend-demo-mapping.md#6-follow-up-actions).

### G5. Explanation visibility

The engine's explanations are complete but technical. Done means: one plain sentence above the
engine text, the three status badges with readable labels, and the full explanation one click
away. Labels and headlines:
[frontend-demo-mapping.md, section 7](frontend-demo-mapping.md#7-status-labels).

### G6. The submission package

Mandatory items are listed in
[nasa-challenge-alignment.md, section 3.1](nasa-challenge-alignment.md#31-mandatory-for-eligibility-and-submission).
Done means:

- every required form field completed in English, from the drafts in D3;
- one demo within the limit: seven slides or thirty seconds;
- demo and final-project links opened successfully in a private browser window;
- the SI question answered truthfully, and the same acknowledgement present in the repository;
- every source listed in the References field;
- the repository front page corrected, because it is what a judge opens first.

The root `README.md` currently describes a Flutter client and labels the algorithms and domains
"not implemented yet". Both statements are out of date. Suggested content for its owner: what
the project is, what works today, how to run the demonstration in one command, the simulated-data
statement, a "Use of SI tools" section, and a link to this folder. `AGENTS.md` and
`frontend/README.md` also name Flutter.

Submit a complete version early on Sunday afternoon. The guide allows resubmission until the
deadline and judges see only the last saved version.

### G7. Claim discipline

Costs nothing and protects the Validity score. Done means every team member can state from
memory: all crew data is simulated; settings are demonstration values; 729 tests verify
software, not science; vital signs and cognition are prototypes and are not shown; `nominal` is
not "healthy"; the heart-rate values in the baseline scenario are authored. Wording guide:
[scientific-evidence-matrix.md, section 5](scientific-evidence-matrix.md#5-wording-guide).

### G8. Demonstration reliability

Storage is in memory and disappears on restart. Done means: a backup screen recording exists as
soon as the primary flow works once; the replay fixture is bundled as an offline fallback; the
demo has been timed against the limit at least twice. Checklist:
[frontend-demo-mapping.md, section 8](frontend-demo-mapping.md#8-reliability-checklist-for-recording-and-judging).

## 4. P1: high value if feasible

### G9 and G10. Provenance and mission phase

Small additions to the Evidence panel: the measurement `source`, the algorithm name and version,
the settings used, the baseline identifier, and the mission phase of the evaluation. All of it
is already in the API responses. Strong signal of rigour for little work.

### G11. A personal reference inside the sleep flow

Today Scene B is a trend screen with no personal reference, and the explanation says so. Adding
one would show steps 3 to 5 of the reasoning chain in a single flow. The API supports it and an
API test covers it. Constraints to respect: the baseline must be built from the **same mission
phase** as the evaluation; its reference window must end before the evaluation window starts; it
must be `established`, which requires explicit criteria and a `policy_source` text. It needs
earlier in-flight nights in the seeded data. It changes Scene B's outputs, so the values in
[primary-demo-flow.md](primary-demo-flow.md) would have to be re-verified. Attempt only after G1
to G8 are done.

### G12. Wording in the vital-signs prototype

The repository is public and will be read. Three comments in
`backend/app/domains/vitals/vitals.py` claim more than their sources support: the ISO standard
as the basis of a per-reading margin, the "false alarm about every 20 days for healthy crew"
sentence, and "normal for spaceflight" in the module description. Details and suggested wording:
evidence matrix items E12 and E14. This is a comment-only change by the module owner.

### G13. Vital-signs evaluation, conditional

Blood pressure and body temperature are named in the challenge, so an integrated evaluation
would help Relevance. It is also the riskiest item on this list: it needs an adapter, a change
to the evaluation command, tests, contract documentation, and answers to the open scientific
issues in E11 to E14, including a temperature margin that would probably flag ordinary variation
often. **Go or no-go at Sunday midday**, and only if G1 to G8 are complete. If no-go, the
existing blood-pressure consistency check on ingestion is a real, working example to mention
when asked about vital signs.

### G14. Live "complete the record"

Entering the two missing nights and watching coverage improve would close the loop from prompt
to action. It involves writes, invalidation of stored evaluations and recomputation, and one
trap: a second record for the same time and device with a different value makes both unusable.
Optional, and only with testing.

## 5. P2: after the hackathon

| Gap | Why not now | What it would take |
| --- | --- | --- |
| G15 Real datasets | A dataset forced in on the last day would be the "superficial addition" the rubric warns against, and no suitable open per-person time series was identified during this work | Identify an open dataset with compatible indicators and usage terms; map it to the contracts; convert units at ingestion |
| G16 Scientific validation | Requires real data and domain review | Characterise false-positive behaviour; configure device ranges from documentation; have settings reviewed |
| G17 Cognition | Needs the test interface, practice-effect corrections and evidence that the emulation matches NASA's battery | See evidence item E15 |
| G18 API resources | Contract changes need the whole team and affect the frontend | Crew and mission endpoints, structured trend fields, durable storage |
| G19 Everything else | Optional in the challenge text; each would dilute the demonstration | RAG assistant, nutrition, other environments, gamification, clickable body figure |

## 6. Suggested ownership

| Person | Responsibility | Items |
| --- | --- | --- |
| Andrea | Integration and submission lead | G2; G6 (form fields, links, repository front page, SI disclosure); G3 content hand-over; G8 with Silvio; G11 if time; go or no-go calls |
| Marco | Scientific lead | G7 (review the evidence matrix and the wording guide; brief the team); G12; slide 6 and the answers in [judge-questions.md](judge-questions.md); decision and work on G13 |
| Silvio | Interface | G1, G5, G4, the Research Lens panel for G3, the Decision Replay slider; then G9 and G10; screenshots and screen capture for G6 and G8 |

These are suggestions. The ownership table in [AGENTS.md](../../AGENTS.md) is still unassigned.

## 7. Suggested timeline

Local time. Adjust to the Local Event's schedule.

| When | Milestone |
| --- | --- |
| Saturday evening | G2 running; astronaut view shows Scene B from real data; G3 content handed to Silvio; G7 briefing; G12 |
| As soon as Scene B works | First backup recording |
| Sunday 12:00 | Primary flow complete: both scenes, Evidence, Research Lens, Action Center. Decide Scene B fallback, G11 and G13 |
| Sunday 15:00 | Feature freeze. Screenshots. Choose slides or video |
| Sunday 17:00 | First complete submission, all links tested in a private window |
| Sunday 17:00 to 21:00 | Polish, timed rehearsals, resubmit |
| Sunday 22:00 | Final submission. Nothing new after this |
| Sunday 23:59 | Deadline |

## 8. What not to do

- Do not add a dataset, a model or a feature in order to mention it. One coherent flow scores
  better than five partial ones.
- Do not present a prototype as a feature.
- Do not let the demo run a second over thirty seconds or a slide over seven.
- Do not change shared contracts on the last day.
- Do not run the backend with auto-reload during a recording.
