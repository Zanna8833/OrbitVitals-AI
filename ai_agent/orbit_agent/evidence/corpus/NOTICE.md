# Evidence corpus: sources, attribution and rights review

`evidence_summaries.json` contains 114 short summaries **written by the OrbitVitals
team** of paragraphs published on 17 public NASA web pages and in 8 open-access
peer-reviewed articles. The summaries are not the sources' text and not quotations.
Neither NASA nor the authors or publishers of the articles wrote, reviewed, approved or
endorsed them, this corpus or the OrbitVitals project. No text copied from a source is
stored in this repository: for each summary the corpus records the source, its section,
and the SHA-256 digest of the summarised paragraph, so that `scripts/verify_sources.py`
can confirm the paragraph is still published.

The NASA insignia, logotype and other NASA identifiers are not used. "NASA" appears only
to name the publisher of a source page, a NASA standard or a NASA programme.

All 25 sources were read on 2026-11-15, and all 114 source paragraphs were found by
digest on that date.

## NASA web pages (17 pages, 67 entries)

Publisher of every page: National Aeronautics and Space Administration (NASA).

| # | Page title | URL | Entries |
| --- | --- | --- | --- |
| 1 | Risk from Inadequate Sleep and Irregular Schedules | https://www.nasa.gov/reference/risk-from-inadequate-sleep-and-irregular-schedules/ | NASA-SLEEP-RISK-01 to 04 |
| 2 | The Human Body in Space | https://www.nasa.gov/humans-in-space/the-human-body-in-space/ | NASA-BODY-* (7) |
| 3 | Risk of Reduced Cardiorespiratory and Musculoskeletal Fitness | https://www.nasa.gov/reference/risk-of-reduced-cardiorespiratory-and-musculoskeletal-fitness/ | NASA-FITNESS-RISK-01 to 03 |
| 4 | Risk of Cardiovascular Adaptations | https://www.nasa.gov/reference/risk-of-cardiovascular-adaptations/ | NASA-CARDIO-RISK-01, 02 |
| 5 | Risk of Behavioral Changes and Psychiatric Disorders | https://www.nasa.gov/reference/risk-of-behavioral-changes-and-psychiatric-disorders/ | NASA-BEHAVIOR-RISK-01 |
| 6 | 5 Hazards of Human Spaceflight | https://www.nasa.gov/hrp/hazards/ | NASA-HAZARDS-* (3) |
| 7 | OCHMO-TB-031 Exercise Overview | https://www.nasa.gov/ochmo-tb-031-exercise-overview-2/ | NASA-TB031-* (5) |
| 8 | Hazard: Gravity Fields | https://www.nasa.gov/hrp/hazard-gravity-fields/ | NASA-GRAVITY-01 to 04 |
| 9 | Hazard: Isolation and Confinement | https://www.nasa.gov/hrp/hazard-isolation-and-confinement/ | NASA-ISOLATION-01 to 04 |
| 10 | Risk of Radiation-Induced Cancers | https://www.nasa.gov/reference/risk-of-radiation-induced-cancers/ | NASA-RADIATION-RISK-01 to 03 |
| 11 | Cardiovascular Health in Microgravity | https://www.nasa.gov/missions/station/cardiovascular-health-in-microgravity/ | NASA-CARDIO-STATION-01 to 05 |
| 12 | Risk of Spaceflight-Induced Bone Changes | https://www.nasa.gov/reference/risk-of-spaceflight-induced-bone-changes/ | NASA-BONE-RISK-01, 02 |
| 13 | Wearable Tech for Space Station Research | https://www.nasa.gov/missions/station/iss-research/wearable-tech-for-space-station-research/ | NASA-WEARABLE-01 to 05 |
| 14 | Science in Space: Week of Sept. 15, 2023 - Sleep on Station | https://www.nasa.gov/humans-in-space/science-in-space-week-of-sept-15-2023-sleep-on-station/ | NASA-SLEEP-STATION-01 to 07 |
| 15 | Peak Performance in Microgravity | https://www.nasa.gov/missions/station/iss-research/peak-performance-in-microgravity/ | NASA-PERFORMANCE-01 to 05 |
| 16 | Counteracting Bone and Muscle Loss in Microgravity | https://www.nasa.gov/missions/station/iss-research/counteracting-bone-and-muscle-loss-in-microgravity/ | NASA-BONE-MUSCLE-01 to 05 |
| 17 | Why Space Radiation Matters | https://www.nasa.gov/missions/analog-field-testing/why-space-radiation-matters/ | NASA-RADIATION-BASICS-01, 02 |

Notes on individual pages:

- Page 5 was first requested as `.../risk-of-behavioral-conditions-and-psychiatric-disorders/`
  and redirects to the URL above.
- Entries NASA-TB031-AEROBIC-01 and NASA-TB031-STRENGTH-01 summarise requirements of the
  NASA standard NASA-STD-3001 (V1 4003 and V1 4024) as listed on page 7. They are NASA
  requirements for spaceflight, not thresholds used by the OrbitVitals backend.
- Pages 13, 14 and 15 describe investigations of ESA and CSA on the International Space
  Station as reported by NASA; the summaries name the agency of each investigation.
- For page 16 the first summarised paragraph precedes the first section heading and is
  recorded under the section name "Opening section".

What was checked for each NASA page:

- **Copyright, licence or permission notices on the text:** none found on any page. The
  pages carry the standard NASA footer and name a page editor and a responsible NASA
  official.
- **Authorship:** page 2 has a byline of two people (2021); the other pages name no
  author of the text. None states whether the text was written by federal employees or
  by contractors.
- **Third-party material:** image credits name NASA or individual photographers; images
  are not used here. Paragraphs that quote a named person were not summarised. Pages 7
  and 16 cite external research articles; none of the summarised paragraphs is a
  citation list, a quotation or a credit line.

## Peer-reviewed articles (8 articles, 47 entries)

Each article is cited by its DOI. The paragraph digests refer to the full text served
by the Europe PMC REST service (`https://www.ebi.ac.uk/europepmc/webservices/rest/<PMCID>/fullTextXML`),
which is the copy `scripts/verify_sources.py` downloads. The licence is the one Europe
PMC lists for the article's open-access copy, read on 2026-11-15.

| # | Article | Journal, year | DOI | Europe PMC | Licence | Entries |
| --- | --- | --- | --- | --- | --- | --- |
| 18 | Wu B et al. On-orbit sleep problems of astronauts and countermeasures | Military Medical Research, 2018 | https://doi.org/10.1186/s40779-018-0165-6 | PMC5975626 | CC BY | LIT-WU2018-01 to 05 |
| 19 | Roy-O'Reilly M, Mulavara A, Williams T. A review of alterations to the brain during spaceflight and the potential relevance to crew in long-duration space exploration | npj Microgravity, 2021 | https://doi.org/10.1038/s41526-021-00133-z | PMC7887220 | CC BY | LIT-ROYOREILLY2021-01 to 07 |
| 20 | Chancellor JC, Scott GBI, Sutton JP. Space Radiation: The Number One Risk to Astronaut Health beyond Low Earth Orbit | Life, 2014 | https://doi.org/10.3390/life4030491 | PMC4206856 | CC BY | LIT-CHANCELLOR2014-01 to 06 |
| 21 | Scott JPR et al. The Role of Long-Term Head-Down Bed Rest in Understanding Inter-Individual Variation in Response to the Spaceflight Environment: A Perspective Review | Frontiers in Physiology, 2021 | https://doi.org/10.3389/fphys.2021.614619 | PMC7904881 | CC BY | LIT-SCOTT2021-01 to 05 |
| 22 | Demontis GC et al. Human Pathophysiological Adaptations to the Space Environment | Frontiers in Physiology, 2017 | https://doi.org/10.3389/fphys.2017.00547 | PMC5539130 | CC BY | LIT-DEMONTIS2017-01 to 07 |
| 23 | Patel ZS et al. Red risks for a journey to the red planet: The highest priority human health risks for a mission to Mars | npj Microgravity, 2020 | https://doi.org/10.1038/s41526-020-00124-6 | PMC7645687 | CC BY | LIT-PATEL2020-01 to 07 |
| 24 | Marshall-Goebel K et al. Assessment of Jugular Venous Blood Flow Stasis and Thrombosis During Spaceflight | JAMA Network Open, 2019 | https://doi.org/10.1001/jamanetworkopen.2019.15011 | PMC6902784 | CC BY | LIT-MARSHALLGOEBEL2019-01 to 03 |
| 25 | English KL et al. High intensity training during spaceflight: results from the NASA Sprint Study | npj Microgravity, 2020 | https://doi.org/10.1038/s41526-020-00111-x | PMC7434884 | CC BY | LIT-ENGLISH2020-01 to 07 |

How the articles were chosen and used:

- Only articles that Europe PMC lists as open access under CC BY (or CC0) were used.
  Candidate articles without such a licence, or with a non-commercial or share-alike
  licence, were left out even though a summary of facts would not copy their text.
- The article version (CC BY 3.0 or 4.0) was not checked beyond Europe PMC's "CC BY"
  label, and the publishers' own pages were not read, because some publisher sites
  refuse automated requests.
- Several articles are reviews. A summary that reports a number from a study cited in
  the review says so ("one cited study found ...") and was written from the review, not
  from the cited study.
- CC BY requires credit to the authors. Every citation carries authors, journal, year
  and DOI, and states that the text is an OrbitVitals summary. The summaries are not
  adaptations of the articles' wording.

## How the summaries were checked

- Each summary was written from the fetched paragraph by one person and compared with
  it by that person. No second reviewer has checked the summaries.
- An automatic scan compared every summary with its source paragraph: no summary shares
  a run of more than 7 consecutive words with it.
- No two entries summarise the same paragraph, and no two summaries share half or more
  of their content words (enforced by the test suite).
- Paragraphs whose main subject is medication were not summarised.
- The numbers in the summaries describe published studies or NASA requirements. They
  are not clinical thresholds and are not used by the OrbitVitals backend.

## Guidance consulted

- NASA Images and Media Usage Guidelines,
  https://www.nasa.gov/nasa-brand-center/images-and-media/ (page dated 2026-10-27): NASA
  content is generally not subject to copyright in the United States; third-party
  copyrighted material is marked; NASA should be acknowledged as the source; use must
  not imply NASA endorsement; the NASA insignia and logotype are not in the public
  domain. Its section "Super Intelligence (SI) Applications" asks that outputs of AI
  products be attributed to the product and not to NASA, prohibits references such as
  "according to NASA", and allows stating that a tool includes NASA source material
  without implying NASA review or permission.
- NASA Brand Center, https://www.nasa.gov/nasa-brand-center/: subject to copyright
  indications and the guidelines, NASA material may be reproduced and distributed
  without further permission; where copyright is indicated, permission is needed from
  the owner.
- NASA STI disclaimers, https://sti.nasa.gov/disclaimers/ (page dated 2026-10-06): works
  of U.S. Government employees are not protected by copyright in the U.S. (17 U.S.C.
  105); contractors and grantees are not Government employees and generally hold
  copyright to works they produce for the Government.
- NPR 2200.2E, https://nodis3.gsfc.nasa.gov/ (Chapters 2 and 4): contractor and
  grantee publishing rights follow their agreements; copyright notices are applied
  where applicable.
- 2026 NASA Space Apps Challenge Participant Terms and Conditions,
  https://www.spaceappschallenge.org/legal/ (updated 2026-08-07): participants must not
  submit material for which they do not hold the rights, original content is
  distributed under an OSI licence (Apache 2.0 if none is named), non-NASA materials
  must be openly available with their licences identified, and every source must be
  cited.
- Europe PMC, https://europepmc.org/: open-access status and licence of each article,
  and the REST service used to download the full text.

## Conclusion

No restriction was found for the NASA pages, but public redistribution of their
original wording could not be established: NASA's guidance says contractor-written work
is generally the contractor's, the pages do not say who wrote each paragraph, and
public domain status under 17 U.S.C. 105 applies in the United States. The articles are
openly licensed, but the same rule is applied to them for consistency. The corpus
therefore stores independent summaries and digests instead of the paragraphs. This is
the project's own review, not legal advice. The repository's Apache 2.0 licence covers
the OrbitVitals summaries and code only; it does not license NASA material or the
articles.
