# Evidence corpus: sources, attribution and rights review

`nasa_summaries.json` contains 25 short summaries **written by the OrbitVitals team** of
paragraphs published on 7 public NASA web pages. The summaries are not NASA text and not
quotations. NASA did not write, review, approve or endorse them, this corpus or the
OrbitVitals project. No text copied from the source pages is stored in this repository;
for each summary the corpus records the source URL, page title and section, and the
SHA-256 digest of the summarised paragraph, so that `scripts/verify_sources.py` can
confirm the paragraph is still published.

The NASA insignia, logotype and other NASA identifiers are not used. "NASA" appears only
to name the publisher of a source page.

## Sources

Publisher of every page: National Aeronautics and Space Administration (NASA). All
pages were last read on 2026-11-15, and all 25 source paragraphs were found on their
page by digest on that date.

| # | Page title | URL | Entries |
| --- | --- | --- | --- |
| 1 | Risk from Inadequate Sleep and Irregular Schedules | https://www.nasa.gov/reference/risk-from-inadequate-sleep-and-irregular-schedules/ | NASA-SLEEP-RISK-01 to 04 |
| 2 | The Human Body in Space | https://www.nasa.gov/humans-in-space/the-human-body-in-space/ | NASA-BODY-* (7) |
| 3 | Risk of Reduced Cardiorespiratory and Musculoskeletal Fitness | https://www.nasa.gov/reference/risk-of-reduced-cardiorespiratory-and-musculoskeletal-fitness/ | NASA-FITNESS-RISK-01 to 03 |
| 4 | Risk of Cardiovascular Adaptations | https://www.nasa.gov/reference/risk-of-cardiovascular-adaptations/ | NASA-CARDIO-RISK-01, 02 |
| 5 | Risk of Behavioral Changes and Psychiatric Disorders | https://www.nasa.gov/reference/risk-of-behavioral-changes-and-psychiatric-disorders/ | NASA-BEHAVIOR-RISK-01 |
| 6 | 5 Hazards of Human Spaceflight | https://www.nasa.gov/hrp/hazards/ | NASA-HAZARDS-* (3) |
| 7 | OCHMO-TB-031 Exercise Overview | https://www.nasa.gov/ochmo-tb-031-exercise-overview-2/ | NASA-TB031-* (5) |

Page 5 was first requested as `.../risk-of-behavioral-conditions-and-psychiatric-disorders/`
and redirects to the URL above. Entries NASA-TB031-AEROBIC-01 and NASA-TB031-STRENGTH-01
summarise requirements of the NASA standard NASA-STD-3001 (V1 4003 and V1 4024) as
listed on page 7; they are NASA requirements for spaceflight, not thresholds used by the
OrbitVitals backend.

## What was checked for each page (2026-11-15)

- **Copyright, licence or permission notices on the text:** none found on any of the 7
  pages. The pages carry the standard NASA footer and list a page editor and a
  responsible NASA official.
- **Authorship:** pages 1 and 3 to 7 name no author of the text; page 2 has a byline of
  two people (2021). None of the pages states whether the text was written by federal
  employees or by contractors.
- **Third-party material:** image credits on the pages name NASA or individual
  photographers; images are not used here.
  Page 7 cites external research articles and credits data in figures. None of the 25
  summarised paragraphs contains a citation of an external study, a quotation of a
  named person or a credit line.

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
  must be openly available, and every source must be cited.

## Conclusion

No restriction was found for these pages, but public redistribution of the original
wording could not be established: NASA's guidance says contractor-written work is
generally the contractor's, the pages do not say who wrote each paragraph, and public
domain status under 17 U.S.C. 105 applies in the United States. The corpus therefore
stores independent summaries and digests instead of the paragraphs. This is the
project's own review, not legal advice. The repository's Apache 2.0 licence covers the
OrbitVitals summaries and code only; it does not license NASA material.
