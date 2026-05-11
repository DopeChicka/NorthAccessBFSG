# NorthAccessBFSG Project State

## Current Main State (2026-05-11)

Main includes:

- Discovery resolver and query planner
- Provider execution foundation (mock + optional Google Places seed provider)
- Company enrichment and qualification precheck
- Promotion gate and website probe (mock + live HTTP foundation)
- Scan readiness and scan job skeleton
- Browser smoke + axe homepage and per-journey execution foundations
- Finding, evidence, compliance mapping, review queue, JSON reports, delta comparison
- Public quick-check API with CORS support
- GitHub Actions CI validation pipeline

Latest validation baseline on main:

- `python -m pytest -q` passes
- guarded pipeline passes
- CI workflow passing

## Accessibility Audit Methodology Alignment

Automation is treated as pre-check signal generation only. It does not provide legal guarantees.

Finding foundation supports manual review workflows with structured metadata:

- category: `accessibility | technical | privacy | seo`
- severity and title/description for triage
- evidence and technical evidence payloads
- source tool traceability
- recommendation text
- responsible role assignment:
  - `developer | content | design | ux | auditor`
- `manual_review_required` defaults to `true`
- findings are role-assigned for implementation ownership:
  - `developer | content | design | ux | auditor`
- legal disclaimer default:
  - `Technischer Hinweis, keine Rechtsberatung. Manuelle Prüfung empfohlen.`

Evidence and compliance mapping remain reference/signal layers for human review and follow-up work.
No overlay promise is part of the methodology.
