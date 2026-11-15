---
id: fire-smoke-inhalation
title: Fire and Smoke Inhalation on a Spacecraft
category: protocol
summary: ISS fire response sequence, breathing protection, combustion products (CO, HCN, HCl), and medical care of crewmembers exposed to smoke; use for any fire alarm, smoke or burning smell.
sources: [https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-008-fire-protection.pdf, https://ntrs.nasa.gov/api/citations/20220019247/downloads/Emergency%20Ops%20History%20for%20SpaceOps%20Conference%202023.pdf, https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-015-spaceflight-toxicology.pdf, https://ntrs.nasa.gov/api/citations/20240007713/downloads/JSC%2020584_SMACs_Rev%20C_FINAL.pdf]
---
## How fire behaves in microgravity

Without buoyant convection, flames in microgravity are roughly spherical, often weaker, and can be pale blue and almost invisible; smoke does not rise, so ISS smoke detectors sit inside the ventilation system [1][2]. Fans can feed a fire with air, which is why the first automatic response is to stop ventilation [1]. Self-feeding fires (an oxygen generator, a lithium-ion battery in thermal runaway) are more dangerous because they do not need cabin oxygen [2]. In oxygen-enriched or higher-pressure atmospheres, materials ignite more easily and burn hotter [1].

The main health hazard besides burns is inhaling toxic combustion products. A small fire can produce large amounts of carbon monoxide (CO), as the 1997 Mir oxygen-generator fire showed [1].

## Recognition

- Fire/smoke alarm (automatic smoke detectors or crew-initiated) [2].
- Visible smoke, flame, or a burning/electrical smell.
- A rise in CO on air-quality monitors; continuous atmospheric sampling can confirm a fire through CO build-up [1].
- Caution messages from failed equipment (helps locate fires behind panels) [2].

Symptoms of CO exposure: headache, dizziness, weakness, upset stomach, vomiting, chest pain and confusion; severity depends on concentration, activity level and duration [3].

## Immediate actions (ISS sequence)

NASA's ISS fire strategy, performed in order until the fire is out [1][2]:

1. **Warn and gather**: alarm, account for all crew at the gathering point; keep a clear path to the return vehicle [2].
2. **Stop ventilation** in the affected module (automatic on smoke detection; oxygen generation also stops) [1][2].
3. **Don breathing protection**. Being in smoke, near the flame, or having symptoms is enough reason to don a mask; do not wait for instrument readings [1]. Portable Breathing Apparatus (PBA, positive-pressure oxygen) is the mask for initial response and egress; respirators with fire cartridges are used for longer searches because a PBA releases oxygen near the fire [2].
4. **Remove electrical power** to the suspected equipment [1].
5. **Use a fire extinguisher**: CO2 extinguishers in the US segment (crew must be on a PBA when discharging CO2 because cartridge respirators do not filter CO2); water-mist extinguishers for open-cabin fires, especially battery fires [1][2].
6. If fire continues, **power down the module**, then evacuate and isolate it [1][2].
7. After extinguishing, isolate the module until scrubbing brings CO, HCN and HCl down to acceptable levels; check air with the handheld combustion product analyzer (CSA-CP) [1][2].

Crew safety comes first: any crewmember may stop and isolate the module if they do not feel safe continuing [2].

## Medical care of an exposed crewmember

Per the NASA fire brief [1]:
1. A crewmember with any symptom of smoke exposure is treated with a supplemental breathing source with eye protection (PBA or the Russian IPK-1M), in a clean-air volume.
2. Consult the flight surgeon for every symptomatic crewmember.
3. Protect skin as well; unknown products may cause irritation.
4. Assess: breathing, SpO2, level of consciousness, burns (face, airway), cough, hoarseness, eye irritation.
5. Burns: see the minor injuries and burns document; facial burns, singed nasal hair, hoarseness or stridor suggest airway injury and need urgent flight surgeon contact.

Oxygen therapy, medications and monitoring duration are set by the flight surgeon / ISS medical checklist.

## Contaminant limits to watch (SMACs)

NASA Spacecraft Maximum Allowable Concentrations (JSC 20584 Rev C, 2024) for key combustion products [4]:

| Contaminant | 1 h | 24 h | 7 d | 30 d | 180 d |
|---|---|---|---|---|---|
| Carbon monoxide (ppm) | 425 | 100 | 55 | 15 | 15 |
| Hydrogen cyanide (ppm) | 8 | 4 | 1 | 1 | 1 |
| Hydrogen chloride (ppm) | 5 | 2 | 1 | 1 | 1 |
| Hydrogen fluoride (ppm) | 3 | 3 | 0.3 | 0.3 | 0.3 |

1-hour and 24-hour SMACs are emergency limits: they may cause reversible effects but should not impair judgment or emergency response [3]. Masks stay on until readings are below the applicable limit and the flight surgeon/toxicologist agrees.

## Exploration vehicles

On Orion (single cabin, about 2% of ISS volume) there is nowhere to evacuate: crew fight the fire with a water-spray extinguisher wearing respirators with fire cartridges, then run a "smoke eater" filter designed to bring the cabin to the 1-hour SMAC within four hours; if needed they don suits and vent the cabin to vacuum [2]. Communication with the ground may be delayed or poor on deep-space missions [1].

## Follow-up and monitoring

- Repeat symptom checks and SpO2/respiratory rate in exposed crew for the following hours; delayed lung symptoms are possible after irritant gas exposure (the Apollo-Soyuz crew developed delayed lung fluid after propellant inhalation) [3].
- Record time in smoke, mask type used, and contaminant readings for the flight surgeon and toxicologist.
- Report every exposed crewmember to the flight surgeon, including those without symptoms.
- Keep the combustion product readings (for example carbon monoxide, hydrogen cyanide, hydrogen chloride, hydrogen fluoride) with their times, so they can be compared with the SMAC limits (see cabin atmosphere reference) [4].
