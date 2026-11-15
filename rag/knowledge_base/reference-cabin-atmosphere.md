---
id: reference-cabin-atmosphere
title: Cabin Atmosphere Limits (Pressure, O2, CO2, Temperature, Humidity, Contaminants)
category: reference-values
summary: NASA-STD-3001 and ISS values for total pressure, inspired oxygen, ppCO2, temperature, humidity and SMAC contaminant limits, plus the atmospheres of ISS, EVA suits and exploration vehicles; use to check live cabin telemetry.
sources: [https://www.nasa.gov/reference/6-0-natural-and-induced-environments-vol-2, https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-004-carbon-dioxide.pdf, https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-003-habitable-atmosphere.pdf, https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-002-eclss.pdf, https://ntrs.nasa.gov/api/citations/20230013523/downloads/Evidence%20Report%20Draft%20Hypoxia%20and%20DCS_20230918.pdf, https://ntrs.nasa.gov/api/citations/20240007713/downloads/JSC%2020584_SMACs_Rev%20C_FINAL.pdf, https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-041-sleep-accommodations.pdf, https://ntrs.nasa.gov/api/citations/20220019247/downloads/Emergency%20Ops%20History%20for%20SpaceOps%20Conference%202023.pdf]
---
## Carbon dioxide (ppCO2)

- **NASA standard**: the 1-hour average ppCO2 in the habitable volume must be **no more than 3 mmHg** (NASA-STD-3001 Vol 2, requirement V2 6004) [1][2]. Earlier requirements allowed 3.8-7.5 mmHg; the limit was lowered on operational and research evidence [2].
- **ISS practice**: since a flight rule limiting the 24-hour average was approved in 2016, ISS CO2 has consistently stayed at or below a 3.00 mmHg 24-hour average, with occasional brief higher excursions; there is slight variation between ISS nodes [2]. Historic ISS range was 1 to 9 mmHg [2].
- **Headache relationship**: each 1 mmHg increase in CO2 doubled the odds of a reported headache; keeping headache risk below 1% would need a 7-day average below 2.5 mmHg [2].
- **Symptoms reported anecdotally**: headaches at 2.8-4.5 mmHg; chronic cough, poor sleep, blurred vision and frontal headache at 3.5 mmHg; fatigue, malaise, decreased sleep and nausea above 4.5 mmHg [2].
- Earth comparison: indoor air about 0.6-0.76 mmHg (0.08-0.1%); 0.5% CO2 = 3.8 mmHg [2].
- Off-nominal CO2 limits are set per program, not in the standard [1]. CO2 is no longer in the SMAC table (deleted in Rev C) [6].
- Local CO2 pockets can form without good ventilation; required ventilation velocity is 4.57-36.58 m/min [1].

## Pressure and oxygen

| Environment | Total pressure | O2 % | ppO2 (mmHg) | Inspired PO2 (mmHg) |
|---|---|---|---|---|
| Sea level / ISS | 14.7 psia (101.3 kPa) | 21 | 160 | 150 |
| ISS airlock campout | 10.2 psia (70.4 kPa) | 26.5 | 140 | 127 |
| Exploration atmosphere (proposed) | 8.2 psia (56.6 kPa) | 34 | 144 | 128 |
| US EVA suit (EMU) | 4.3 psia (29.7 kPa) | 100 | 222 | 175 |

Source: NASA Hypoxia/DCS Evidence Report table [5].

- ISS cabin pressure is typically kept at 14.7 psia [3]. Total pressure must always stay well above 0.91 psi (47 mmHg), where body fluids vaporize (ebullism) at 37 °C [3].

- Indefinite exposure range for total pressure: **above 5.0 psia and up to 15.0 psia** (34.5-103 kPa) [1].
- Normoxia target for inspired PO2: **145-155 mmHg** [4]. A mildly hypoxic PIO2 of 127 mmHg is accepted indefinitely only with a health monitoring plan [1].
- Hyperoxic practical limit: PIO2 333 mmHg [1]. At least 30% diluent gas (nitrogen) is required to prevent lung atelectasis [1].
- Rate of pressure change above 1 psi must not exceed 13.5 psi/min [1].
- ISS rapid depressurization minimum: 490 mmHg (9.5 psia); crew must reach a safe haven before this is reached [8].

## Temperature and humidity

- **Health limits** (NASA-STD-3001 V2 6012): envelope anchored at 18 °C / 75% RH and 27 °C / 25% RH; outside it crew may get dry or irritated mucous membranes, skin rashes from microbial growth at high humidity, overheating [1].
- **Performance/comfort zone** (V2 6013): about 20-25 °C and 30-60% RH [1][4].
- **ISS actual**: 18-27 °C and 30-65% RH [7].
- Humidity is kept above 25% also to prevent static electricity [1].

## Trace contaminants (SMACs)

Spacecraft Maximum Allowable Concentrations, JSC 20584 Rev C (2024), ppm [6]:

| Contaminant | 1 h | 24 h | 7 d | 30 d | 180 d | 1000 d |
|---|---|---|---|---|---|---|
| Ammonia | 30 | 20 | 3 | 3 | 3 | 3 |
| Carbon monoxide | 425 | 100 | 55 | 15 | 15 | 15 |
| Formaldehyde | 0.8 | 0.5 | 0.1 | 0.1 | 0.1 | 0.1 |
| Hydrogen cyanide | 8 | 4 | 1 | 1 | 1 | not set |
| Hydrogen chloride | 5 | 2 | 1 | 1 | 1 | not set |
| Hydrogen fluoride | 3 | 3 | 0.3 | 0.3 | 0.3 | 0.3 |
| Benzene | 40 | 6.7 | 0.5 | 0.1 | 0.07 | 0.013 |

1-h and 24-h values are emergency limits; long-duration values are for continuous exposure.

## Red flags for the assistant

- ppCO2 1-hour average above 3 mmHg, or a rising multi-day trend, especially with crew headaches: notify crew/ground (see CO2 headache document).
- Falling total pressure or ppO2 outside the normoxia target: possible leak (see rapid depressurization document).
- Any contaminant at or above its 24-hour SMAC: toxic atmosphere response.
- Temperature or humidity outside the health envelope for long periods: discomfort, skin and mucosal problems, poor sleep.
