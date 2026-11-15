# OrbitVitals AI — Submission kit (draft)

Working draft for the NASA Space Apps Challenge 2026 submission. **Everything marked “to confirm” must be checked by the team on spaceappschallenge.org** before submitting.

## 1. What we know about the rules (checked 14 Nov 2026)

The official site could not be opened from the development machine (TLS certificate error), so the points below come from **web-search results that quote the official Project Submission Guide and Participant FAQ**, plus secondary event listings. Confirm each one on the official pages: [Project Submission Guide](https://www.spaceappschallenge.org/resources/project-submission-guide/), [Participant FAQs](https://www.spaceappschallenge.org/resources/participant-faqs/), [Judging & Awards Guide](https://www.spaceappschallenge.org/resources/judging-awards-guide/), [2026 event page](https://www.spaceappschallenge.org/2026/).

| Topic | What the sources say | Status |
|---|---|---|
| Dates | Hackathon 14–15 Nov 2026 | to confirm |
| Deadline | Submit from the team page (Project tab → edit → submit) **before Sunday 15 Nov, 11:59 p.m.**; Universal Event teams use the Team Owner’s local time | to confirm |
| Language | English on the project page and in linked materials; the demo video may be spoken in another language | to confirm |
| Project Demo | Required. Not uploaded to the Space Apps site: a **public link** (e.g. YouTube, Google Drive) with no login or permission needed | to confirm |
| Minors | No images, video, audio or likeness of persons under 18 in demos | to confirm |
| AI tools | Permitted; the submission **must describe how AI tools were used** | to confirm |
| References | All external resources (code, text, images, even open source) must be listed in the **References** field | to confirm |
| Rights | Participants must hold the rights to all materials included | to confirm |
| NASA name/logo | No specific rule found. Our project uses no NASA logo and claims no endorsement | to confirm |

## 2. Fit with the challenge

**Challenge statement** (as provided by the team on 14 Nov 2026; title from search results — confirm the title, objectives and listed NASA resources on the challenge page):

> Long-duration missions expose astronauts to space radiation, isolation and confinement, altered gravity, and a hostile closed environment, which can bring immune changes, bone loss, cardiovascular events, and behavioral health problems. On long missions, astronauts carry much of the responsibility for spotting these changes in themselves. Your challenge is to build a health monitoring software that gathers health indicators and enables astronauts to evaluate and act on the status of their health.

Key requirements read from it: (1) gather health indicators; (2) the **astronaut** evaluates their own status; (3) the astronaut can **act**; (4) context: **long-duration** missions, where the crew carries much of the responsibility. The statement does not mention colour coding: that advice must come from another page (guide or FAQ) — to find.

**Where we fit**
- Health monitoring of crew members, with data quality, freshness and activity context made explicit.
- An astronaut-facing view (Crew view) and a ground-facing review (Flight Surgeon).
- Per-person baseline (personal historical range) instead of population thresholds.

**Tension to decide as a team** (the code was not changed for this):
- The challenge wording, as reported, puts the **astronaut** at the centre and stresses long missions. Our interviews pointed the other way for the MVP: during demanding activities, showing many parameters to the astronaut can distract them (Carlucci/Paciucci, Torchia), and the hard question is whether an anomaly is real (Ongaro) — so we centred the **Flight Surgeon** and kept the crew view minimal. Distant missions and on-board autonomy are explicitly out of scope (`UX_ANALYSIS.md` §6).
- Recommended framing: present this as a **deliberate, evidence-based choice** — “who should see what, when” — and name crew autonomy on distant missions as the next step, not as something we already solve.
- We use **no NASA dataset**. If the challenge lists required NASA resources, we must say how they would be used (e.g. NASA OSDR for baselines, after checking licence and content) and must not claim we used them.

## 3. Draft project page text (English, to paste and adapt)

> **OrbitVitals AI — is this reading real, recent and in context?**
>
> Remote health monitoring does not fail only for lack of data. Our interviews with seven professionals — space physiology, signal processing, a wearable sleep monitor, a suborbital crew, aerospace medicine and a former ESA flight surgeon — converged on a different question: *can the person assessing the data tell a physiological change from a measurement problem, and see when and during what activity it was recorded?*
>
> OrbitVitals AI is a web prototype that explores that question with **simulated data**. The **Flight Surgeon review** shows, for each crew member, how fresh the latest data is and the quality of every sample; aligned charts with a shared cursor put heart rate, SpO₂, respiratory rate and motion on one time axis with the scheduled activity, the person’s own historical range from previous sessions and explicit gaps. The **event detail** explains why an item was flagged (a demo rule, never a clinical threshold), separates *observed data* from *interpretation written by people*, and shows data provenance. The **crew view** gives the astronaut only what they need — is data being collected, what is scheduled, any message from the medical team — with values available on request.
>
> **What it is not.** Not a medical device: no diagnosis, no treatment advice, no clinical alarms, no reliability claims. All data is synthetic. Not affiliated with or endorsed by NASA or ESA. There is no AI model in the product: no evidence in our research called for one at this stage.
>
> **How it was built.** React + TypeScript, hand-written SVG charts, no runtime dependencies beyond React. Deterministic synthetic data with five demo scenarios (consistent data, uncertain quality, stale data, lost link, value outside personal range) and an optional live replay. Keyboard accessible; state never conveyed by colour alone. A proposed REST contract lets the backend replace the simulated data source without changing the UI.
>
> **Next.** Usability tests with physicians on simulated cases; integration with the team’s backend; crew autonomy for missions far from Earth.

**Use of AI tools (required statement — adapt):**
> We used an AI coding assistant as a coding and writing assistant: to help draft the UX analysis from our interview notes, write and refactor the frontend code and tests, and translate the documentation into English. All outputs were reviewed and edited by the team. The interviews, the research synthesis and the design decisions are our own. The product itself contains no AI features.

**References (to complete):**
- Interview synthesis, OrbitVitals team, 13 Nov 2026 (`docs/research/`) — participants: M. Cerri, D. Simeone, M. De Vittorio, P. Carlucci, L. Paciucci, F. Torchia, F. Ongaro (check consent before naming them publicly).
- React and React DOM (MIT); Vite, Vitest, TypeScript, oxlint (development tools).
- AI coding assistant, see statement above.
- No external dataset, image or font is used.

## 4. Demo script (≈ 2½ minutes)

1. **(15 s) Problem.** “The question is not only *what* the value is, but whether it is real, recent and in context.” Point at the footer and the *Demo* menu: demo prototype, simulated data.
2. **(30 s) Medical · Review — Full session.** Left list: three items to review, each with its reason and time; crew list with freshness (Crew C *No data since 10:22 UTC*). One screen, list on the left, detail on the right.
3. **(40 s) Event “Signal quality to check” (Crew B, SpO₂).** SpO₂ drop drawn with uncertain/poor markers and gaps; switch on *Compare other signals*: motion is high at the same time (shared cursor). Observed figures: 0 reliable samples in the window. Message: “this looks like a measurement problem, not physiology — and the UI says so without diagnosing.”
4. **(30 s) Event “Value outside personal range” (Crew A, HR).** Good-quality signal above the person’s own P10–P90 band from previous sessions; the rule is a demo rule, not a clinical threshold. Add a note; set status *In review*; send a predefined message.
5. **(20 s) Crew · Today.** Before step 4, send Crew B “check the sensor” from its event: Crew B’s *Now* card now says *After this activity: check the placement of your pulse oximeter (finger)* — the system never asks on its own. Then Crew A: the summary card shows the 4-day change in resting heart rate against the personal range; share it, and it appears in Medical.
6. **(15 s) Live replay + scenario 4.** *Demo* menu → *Live replay*, then *No connection*: at 10:34 the link drops and the screen says the data is the last received.
7. **(10 s) Close.** Hypothesis, not a validated tool; next: tests with physicians.

## 5. Checklist

- [ ] Confirm deadline, language, demo and AI-disclosure rules on the official pages (§1).
- [ ] Read the official challenge statement and resources; adjust §2 and the project text.
- [ ] Decide the framing of the Flight Surgeon / astronaut tension (§2).
- [ ] Record the demo (no minors on screen), upload it with a public link.
- [ ] Publish the repository (if required) — *team decision: nothing has been pushed yet*.
- [ ] Paste the project text, AI statement and references; check participant consent before naming interviewees.
- [ ] Screenshots available in `docs/screenshots/`.
