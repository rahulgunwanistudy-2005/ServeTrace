# Sources

Everything ServeTrace states about the law or about the scale of the problem traces to one
of these. The Methodology page cites them. Nothing outside this list may be asserted as
fact in the product, in generated documents, or in the write-up.

## The problem

- Pew Charitable Trusts, *How Debt Collectors Are Transforming the Business of State
  Courts* (2020) — more than 70% of debt collection suits end in default judgment.
  https://www.pew.org/en/research-and-analysis/reports/2020/05/how-debt-collectors-are-transforming-the-business-of-state-courts

- New York Focus, *5 key takeaways on sewer service* (June 2025) — roughly 17% of 366,000
  NYC consumer credit suits were answered between 2019 and 2023; about 152,000 default
  judgments were entered between 2019 and 2024.
  https://nysfocus.com/2025/06/11/nyc-process-servers-investigation

## The law encoded in the engine

Each item maps to an L-id in `CLAUDE.md` §5. No legal statement may appear anywhere in the
product that is not traceable to one of these rows.

- **L1, L2, L3 — CPLR § 308**, methods of personal service on a natural person: personal
  delivery (308(1)), delivery to a person of suitable age and discretion plus mailing
  (308(2)), and affix-and-mail after due diligence (308(4)).
  https://codes.findlaw.com/ny/civil-practice-law-and-rules/cvp-sect-308/

- **L4 — Due diligence in practice.** Courts commonly expect documented attempts at
  varying times and days; a common practitioner standard is three attempts on at least two
  different days at different times of day. Presented in the product as what courts
  commonly expect, never as a statute.
  https://jtnylaw.com/2020/04/cplr-3085/

- **L5 — CPLR § 5015(a)(4)**, vacating a judgment for lack of jurisdiction, which includes
  improper service. A disputed service claim may lead the court to order a traverse
  hearing.
  https://forms.runsensible.com/blog/general-article/vacate-a-default-judgment-nyc/

- **L6 — CPLR § 317.** A person served other than by personal delivery who did not
  personally receive notice in time to defend may move within one year after learning of
  the judgment, and no more than five years after entry, with a meritorious defence.
  https://forms.runsensible.com/blog/general-article/vacate-a-default-judgment-nyc/

- **L7 — GPS recording by licensed NYC process servers.** NYC Admin Code § 20-410 and
  6 RCNY § 2-233b require a licensed process server to carry a device that electronically
  records the GPS location, date and time of each service or attempt. DCWP accepts
  complaints from legal advocates.
  https://www.nyc.gov/site/dca/businesses/info-process-servers.page
  https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCrules/0-0-0-149059

## Geocoding

- NYC Planning Labs GeoSearch — free, no API key.
  https://geosearch.planninglabs.nyc/v2/search

## Map tiles

- OpenFreeMap, Liberty style. https://tiles.openfreemap.org/styles/liberty
