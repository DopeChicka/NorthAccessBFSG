\# NorthAccessBFSG Project State



\## Current Main State



Latest validated main after PR #10:



\- pytest: 56 passed

\- guarded pipeline: passed

\- Promotion Gate merged



\## Completed Work



\### PR #5 - Lead Discovery City Resolver



Added:

\- data/orte\_deutschland.csv

\- place resolver

\- discovery keyword groups

\- discovery endpoints



Validated:

\- Lübeck / Luebeck / lubeck resolution works



\### PR #6 - Discovery Query Planner



Added:

\- DiscoveryRun

\- LeadCandidate

\- deterministic query planner

\- persisted discovery runs



Flow:

City -> postal codes -> keyword groups -> query\_plan -> DiscoveryRun



\### PR #7 - Mock Provider Execution



Added:

\- provider abstraction

\- mock provider

\- provider execution service

\- mock candidates persisted as LeadCandidate rows



\### PR #8 - Google Places Seed Provider and Qualification Precheck



Added:

\- Google Places provider foundation

\- disabled by default

\- CompanyQualification

\- qualification precheck endpoints



Important:

Google Places results are seed candidates only.

They are not proof of BFSG applicability.



\### PR #9 - Company Enrichment Foundation



Added:

\- CompanyEnrichment

\- enrichment provider abstraction

\- mock company enrichment

\- qualification uses enrichment signals



No live Northdata integration yet.



\### PR #10 - Promotion Gate Foundation



Added:

\- PromotionDecision

\- promotion service

\- promotion endpoints



Statuses:

\- rejected

\- needs\_review

\- ready\_for\_website\_probe



Important:

PromotionDecision is internal routing only.

It is not a legal conclusion.



\## Current Open Work



\### PR #11 - Website Probe Foundation



Branch:

codex/website-probe-foundation



Goal:

Add WebsiteProbe model/service/endpoints and deterministic mock provider.



Scope:

\- no live website fetching

\- no scraping

\- no Playwright changes

\- no accessibility audit

\- no legal conclusion



Needs validation:

\- py\_compile

\- guarded pipeline

\- pytest

\- Docker/API curl flow

