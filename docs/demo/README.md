# Demonstration and submission strategy

Competition alignment, scientific evidence audit and demonstration plan for OrbitVitals AI at
the NASA Space Apps Challenge 2026.

Prepared on 2026-11-14 against commit `667f512`. OrbitVitals AI is a research prototype, not a
medical device. All crew data in the project is simulated.

## Bottom line

- **The deadline is Sunday, November 15 at 11:59 p.m. local time.** The demo must be a video of
  30 seconds or less, or a deck of at most seven slides. Exceeding either removes eligibility
  for Global Judging. Both limits are confirmed in the official 2026 guides.
- **The challenge is astronaut-first and visual.** NASA asks for "a visual tool that helps
  astronauts assess their own health ... and provides guidance on treatments and health
  improvements". The backend is strong; no interface is in this repository, and nothing yet
  tells the astronaut what to do next.
- **Our distinctive capability is trust before interpretation.** The system answers three
  questions separately (can I trust this measurement, what is my own reference in this mission
  phase, what changed over time), explains each answer, and says "not enough data" when that is
  true.
- **Our weakest judging criterion is Relevance.** No NASA dataset enters any computation. NASA
  resources inform the design. That must be visible in the product and stated honestly.
- **The recommended demonstration is a two-scene contrast on sleep data**: a faulty reading that
  is correctly treated as a measurement problem, and a slow decline that no single night
  reveals. Both were verified today through the real engines and the real API.

## Documents

| Document | Read it for |
| --- | --- |
| [nasa-challenge-alignment.md](nasa-challenge-alignment.md) | The official brief, mandatory rules, judging criteria, compliance matrix and competition risks |
| [scientific-evidence-matrix.md](scientific-evidence-matrix.md) | What each scientific claim rests on, which sources were checked, the wording guide and the reference list |
| [primary-demo-flow.md](primary-demo-flow.md) | The two scenes, step by step, with the engines' actual outputs and how to reproduce them |
| [frontend-demo-mapping.md](frontend-demo-mapping.md) | Screens, data sources, missing API resources, follow-up actions and status labels |
| [presentation-storyboards.md](presentation-storyboards.md) | Narrative, 90-second and extended demonstrations, the 30-second video and seven-slide versions, project page drafts |
| [judge-questions.md](judge-questions.md) | Thirty likely questions with defensible answers |
| [prioritized-gaps.md](prioritized-gaps.md) | P0, P1 and P2 actions, owners and a timeline to the deadline |

Suggested reading by role: Andrea starts with the gaps and the alignment; Marco with the
evidence matrix and the judge questions; Silvio with the frontend mapping and the primary flow.

## What exists today

Verified by reading the code and running it. "Demonstrated" means a reproducible run exists in
the repository.

| Component | State | Basis |
| --- | --- | --- |
| Data Quality Engine | Implemented and demonstrated | Tests; replay; HTTP ingestion |
| Personal Baseline Engine, by mission phase | Implemented and demonstrated | Tests; replay `personalized_baseline`; baseline command |
| Sleep monitoring and trend screen | Implemented and demonstrated | Tests; replay; HTTP run on 2026-11-14 |
| Physical activity monitoring | Implemented and demonstrated | Tests; replay; documented HTTP workflow |
| FastAPI application, in-memory storage | Implemented and demonstrated | 729 tests pass |
| Five reproducible scenarios | Implemented and demonstrated | `replay all --validate` exits 0 |
| Vital signs (blood pressure, temperature) | Experimental prototype | Code only; no tests; not reachable through the API |
| Cognition scoring | Experimental prototype | Standalone command-line scorer; no tests; no API |
| Follow-up actions and guidance | Missing | Not in the API; proposed as interface behaviour |
| NASA evidence in the product | Planned | Content prepared in this folder; RAG module is a placeholder |
| Interface | Not in this repository | `frontend/` is a placeholder README |
| Nutrition | Placeholder | Empty package |
| Crew list and mission timeline endpoints | Not implemented | Listed as open points in the contract |

The crew data seeder and the sleep HTTP demonstration are being built on other branches. They
were not reviewed for this package.

## The five actions that matter most

1. Build the astronaut view for the two-scene flow and connect it to seeded data.
2. Put NASA Human Research Program content next to every finding, and describe NASA resource use
   precisely in the submission form.
3. Give every finding a next step and a summary for the flight surgeon.
4. Complete the submission package early: form fields, a demo within the limits, public links,
   SI disclosure, references, and an accurate repository front page.
5. Hold the line on claims: simulated data, demonstration settings, prototypes named as
   prototypes.

Details, owners and a timeline are in [prioritized-gaps.md](prioritized-gaps.md).

## Verification record

Commands run on 2026-11-14 from `backend/`, with Python 3.11.9:

| Check | Result |
| --- | --- |
| `python -m pytest` | 729 passed |
| `python -m ruff check .` | All checks passed |
| `python -m ruff format --check .` | 100 files already formatted |
| `python -m scripts.export_schemas --check` | Schemas are up to date |
| `python -m app.scenarios replay all --validate` | Exit code 0; every expectation passed; 765 embedded contract payloads validated |
| Scene A and Scene B fixtures through the HTTP API on a local server | Statuses, quality assessments and explanations match the replay, as recorded in [primary-demo-flow.md](primary-demo-flow.md) |
| Blood-pressure pairing check through `POST /measurements` | Both values returned `unusable` with a written reason |
| `vital_signs` evaluation request | Rejected with status 422, as documented |

Official competition pages and scientific sources were read on the same day. What could not be
verified is listed in [nasa-challenge-alignment.md](nasa-challenge-alignment.md#1-sources-and-how-they-were-verified)
and in [scientific-evidence-matrix.md](scientific-evidence-matrix.md#6-verification-limitations).

No file outside `docs/demo/` was created or changed. Nothing was committed.

## Limits of this package

- It is a plan and an audit, not a code review. A full review is intended after integration.
- The interface could not be inspected, so every screen direction is a proposal.
- Passing tests show that the software behaves as specified. They are not scientific or clinical
  validation, and nothing in this folder should be read as such.

## How this package was produced

Drafted with an AI coding assistant at the team's request, from the repository and from
the public sources cited. The team is responsible for reviewing it before relying on it. This
note is part of the SI disclosure that the Space Apps rules require.
