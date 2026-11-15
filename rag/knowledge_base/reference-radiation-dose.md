---
id: reference-radiation-dose
title: Radiation Dose Limits and Typical Mission Doses
category: reference-values
summary: NASA career and solar particle event dose limits, typical ISS daily dose, projected deep-space and lunar doses, and how to read personal dosimeter values; use to put a crewmember's dose reading in context.
sources: [https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-020-radiation-protection.pdf, https://www.nasa.gov/wp-content/uploads/2023/10/lsah-newsletter-2023-vol28-issue2.pdf, https://standards.nasa.gov/sites/default/files/standards/NASA/C//nasa-std-3001-vol-1-rev-c-signature.pdf, https://www.nasa.gov/hrp/hazard-space-radiation/, https://www.nasa.gov/reference/risk-of-radiation-induced-cancers/, https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp, https://humanresearchroadmap.nasa.gov/evidence/reports/Degen.pdf, https://humanresearchroadmap.nasa.gov/evidence/reports/HRP-ER-CANCER-SR-20260811.pdf]
---
## Units

- **Absorbed dose** (gray, Gy; mGy) is the measured physical energy deposited; it is what dosimeters measure [2].
- **Effective dose** (sievert, Sv; mSv) is calculated from absorbed dose, accounting for how harmful the radiation type is and how sensitive each organ is; all NASA limits are expressed in effective dose (mSv) [1][2].
- In space radiation, effective dose in mSv is numerically larger than absorbed dose in mGy because heavy charged particles are weighted more. Do not compare a mGy reading directly with an mSv limit.

## NASA limits (NASA-STD-3001 Vol 1 Rev C)

- **Career limit**: total career effective dose from spaceflight **less than 600 mSv** (V1 4030) [3], the same for all ages and sexes. It is set so that every crewmember (all ages and sexes) stays below a 3% mean risk of exposure-induced cancer death (REID) above the non-exposed baseline; the dose is calculated with 35-year-old female model parameters for both sexes [1][2].
- **Solar particle events (SPE)**: the vehicle must protect the crew from the design-reference SPE (sum of the October 1989 events) to **less than 250 mSv** effective dose (V1 4031) [3][1].
- **Galactic cosmic rays** (systems supporting crew more than 60 days): design to keep effective dose rate below **1.3 mSv/day in free space** and **0.9 mSv/day on planetary surfaces** (V1 4033) [3][1].
- **On-board nuclear technologies**: less than 20 mSv per mission year (V1 4032; about 0.05 mSv/day, i.e. 10% of an estimated 0.5 mSv/day surface environment) [3][1].
- **ALARA**: exposure must be kept as low as reasonably achievable even below limits (V1 4029) [3][1].

## Typical doses

- Earth natural background: about 2.4 mSv per year [2].
- **ISS**: effective dose on the order of **0.5 mSv per day** [2]; average skin absorbed dose rate about **0.2 mGy per day**, i.e. about 36 mGy for a 180-day expedition [2].
- A 1-year ISS mission at solar minimum: NASA effective dose about 253 mSv for a 35-year-old [2].
- **Beyond low Earth orbit** (lunar transit, Mars): on the order of 1 mSv per day or more [2].
- **Lunar surface**: NASA projects on the order of 0.5 mSv per day, because the Moon itself provides some protection [2]. (This is a projection; independent lunar surface measurements may differ, so treat it as approximate.)
- Apollo skin dose rates ranged from 0.15 to 1.27 mGy/day; Artemis I (uncrewed) measured 0.40 mGy/day in water [2].

Galactic cosmic ray flux varies with the solar cycle [1], and ISS dose also depends on orbit altitude, so daily readings fluctuate; use the crewmember's own running average as the reference.

## How doses are monitored

- Each astronaut wears an active personal dosimeter with real-time telemetry; area monitors placed around the vehicle give time-resolved absorbed dose [2].
- NASA-STD-3001 Vol 2 requires intravehicular area monitoring, personal monitoring, alerting of elevated exposure rates and external space weather monitoring [1].
- The Space Radiation Analysis Group (SRAG) at JSC combines crew-worn dosimeter and area monitor data to determine each crewmember's mission exposure, and provides pre-flight and EVA exposure projections [2].

## How the 600 mSv career limit is derived (2026 evidence report)

The NASA Evidence Report on ionizing radiation carcinogenesis (HRP, approved for public release 2026, read in full) states that the career limit restricts an astronaut's lifetime dose to 600 mSv, derived with NASA's cancer risk model NSCR (latest version NSCR2020) and implemented as a single dose limit corresponding to a 3% mean risk of exposure-induced death (REID) for a 35-year-old, never-smoker, female astronaut, applied to all crew regardless of sex, age and smoking status [8]. It was reviewed by the National Academies, and the report says it was changed from a risk limit to a dose limit in January 2022 with NASA-STD-3001 Volume 1 Revision B [8]. This agrees with the 600 mSv, 3% REID and 35-year-old female basis given in the limits section above (from Volume 1 Rev C); the report adds the never-smoker detail and the history. The report calls the limit conservative, associated with less than a 3% increase in cancer mortality, with lower projected risk for older astronauts and for males [8].

Other points from the same report [8]:
- Planned Design Reference Missions have estimated effective doses in the range 50 to 2000 mSv; the report's table by mission is not reproduced here.
- The limit is lower than the 1 Sv limit of NASA's international partner agencies. Currently planned Mars missions exceed the NASA limit (roughly twice it, according to the report), so they would need an agency-level informed consent process through the Office of the Chief Health and Medical Officer waiver process.
- Cancer is not expected to appear within the timeframe of the mission itself, even for a 3-year Mars mission, so it is a long-term health risk and not an operational risk during flight. The estimated mission doses do not include prior mission doses or medical exposures.
- Uncertainty remains: evidence is extensive above 100 mSv for low-LET radiation, but uncertain below 100 mSv, at low dose rates, and when transferring risk between populations; radiation quality (heavy ions, neutrons) is a major source of uncertainty.
- Astronauts are likely to exceed the limit given longer missions and multiple assignments; NASA is researching countermeasures, cancer surveillance and pharmacological interventions.

## Neutrons and the CANS instrument

The Canadian Space Agency (CSA) states that neutron radiation contributes about 30% of total radiation on the ISS and is especially harmful because it can cause serious biological damage and require specialized protective measures [6]. The page says "total radiation" and does not say whether this is absorbed dose or dose equivalent, so do not use 30% as a conversion factor and do not mix it with the mSv values above.

In February 2026 the CSA awarded a contract of 5.5 million Canadian dollars to Bubble Technology Industries to continue developing CANS, the Canadian Active Neutron Spectrometer, a compact autonomous instrument that measures neutron exposure continuously [6]. It is an instrument in development: the CSA page does not describe it as part of crew dosimetry on board. NASA's carcinogenesis report likewise lists neutrons, with lighter ions, as a significant percentage of the space radiation environment [8]. Earlier Canadian detectors on the ISS include bubble detectors, MOSFET, EVARM and Radi-N and Radi-N2 [6].

## Health effects of space radiation

NASA lists these effects of radiation exposure: increased cancer risk, damage to the central nervous system, altered cognitive function, reduced motor function and behavioral changes [4]. Beyond cancer, exposure may raise the risk of degenerative disorders of the heart, blood vessels and eyes, may affect the central nervous system with cognitive or performance impairment during missions, and may raise the risk of later degenerative conditions [5]. NASA is developing health surveillance practices, medicines to counter radiation effects and personalized cancer risk assessments based on radiation dose and genetic factors [5]. These are research directions; the sources give no in-flight numbers for these effects. Missions to the space station stay inside Earth's magnetosphere, while missions to the Moon and Mars go beyond it [5].

## Degenerative effects: heart, lens and others (2016 report)

The NASA Evidence Report on cardiovascular disease and other degenerative tissue effects from radiation (2016, read in full; older than the other sources in this document) says degenerative effects such as cardiovascular disease, cataracts and respiratory or digestive diseases are documented after terrestrial radiation exposure, but for space radiation the low-dose thresholds, dose-rate and radiation quality effects and mechanisms are not well characterized, and no acceptable model for projecting degenerative risk is available [7]. The conditions of concern listed are cardiovascular disease (ischemic heart disease, atherosclerosis, cardiomyopathy, stroke), cataracts, accelerated aging effects, and immune and endocrine dysfunction [7]. Risk factors such as obesity, alcohol and tobacco use confound the estimates [7].

Cataracts are the effect with astronaut data: among 295 astronauts in the NASA Longitudinal Study of Astronaut Health, cataract incidence was higher in those with higher lens dose (average 45 mSv versus 8 mSv), and higher in those who flew high-inclination or lunar missions with more high-LET heavy ions [7]. A later study of 224 astronauts and 200 controls (NASCA) confirmed an association of space radiation with cortical and posterior subcapsular cataracts, though the study ended early and some results did not reach significance [7]. The report says these cardiovascular and other degenerative risks remain debatable for ISS or short lunar missions but are more likely on long lunar or Mars missions, and that for a Mars mission epidemiology and preliminary estimates suggest a significant cardiovascular risk [7]. In the same report, US astronauts as a group showed lower circulatory disease mortality than the US average (a healthy worker effect) [7]. The report prints short-term and career organ limits (lens, skin, heart, central nervous system) taken from NASA-STD-3001 Volume 1 Revision A; they are not repeated here because the current revision (Rev C) was not checked for them. Treat this 2016 report as background, not as a current limit.

## Red flags for the assistant

- A sudden, sustained step increase in dose rate well above the usual daily rate: possible SPE, see the solar particle event document; alert crew and ground.
- Cumulative mission dose projected to exceed the remaining career allowance (600 mSv minus prior career dose).
- Symptoms of acute radiation syndrome (nausea, vomiting, fatigue, skin injury) after a large SPE [1]: urgent flight surgeon contact.
