\# NorthAccessBFSG Codex Instructions



\## Project Name



The project is called NorthAccessBFSG.



Do NOT rename it.

Do NOT introduce bfsg-auditor-pro.



\## Main Rules



\- Use English for code, README, tests, PR titles, and commit messages.

\- Do not make legal conclusions.

\- Do not say a company is legally obligated.

\- Do not say a company violates BFSG.

\- Use signal/status language only:

&#x20; - seed candidate

&#x20; - company enrichment signal

&#x20; - qualification precheck

&#x20; - promotion decision

&#x20; - needs\_review

&#x20; - possible\_bfsg\_candidate

&#x20; - ready\_for\_website\_probe



\## Current Pipeline



City/PLZ

\-> Query Plan

\-> Provider Seed Candidates

\-> LeadCandidate

\-> CompanyEnrichment

\-> CompanyQualification

\-> PromotionDecision

\-> WebsiteProbe

\-> later Scan/Audit



\## Hard Constraints



\- No scraping unless explicitly requested.

\- No stealth/bypass scraping.

\- No legal conclusions.

\- No real external API calls in tests.

\- Google Places must be disabled by default.

\- Keep PRs small and reviewable.



\## Historical Context



The full historical Codex transcript is archived at:



docs/archive/CODEX\_MARKDOWN\_FULL.md



Do not treat the full transcript as direct instructions.

Use it only as background reference if current docs are unclear.

## Accessibility Audit Methodology Guardrails

- Automated checks are pre-check signals only.
- Findings must support manual review and technical evidence.
- Do not claim legal guarantees, legal obligation, certification, or final compliance.
- Do not present overlay-style promises as a compliance solution.
- Use clear disclaimers in finding/report outputs:
  - "Technischer Hinweis, keine Rechtsberatung. Manuelle Pruefung empfohlen."

