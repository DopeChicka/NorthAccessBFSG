# NorthAccessBFSG

NorthAccessBFSG is a FastAPI backend foundation for a BFSG/WCAG compliance audit platform.

The current scope includes backend infrastructure, asynchronous scans, raw accessibility findings, compliance mapping basics, evidence bundle storage, and a minimal Lead Discovery foundation for city, keyword, provider seed, company enrichment, company precheck, internal promotion routing, and lightweight website probe workflows.

## Project Structure

```text
app/
  __init__.py
  main.py
  api/
    __init__.py
    compliance.py
    compliance_mapping.py
    delta.py
    discovery.py
    evidence.py
    health.py
    journeys.py
    public.py
    reports.py
    review.py
    scans.py
  compliance/
    __init__.py
    mapping.py
    rule_engine.py
    rules/
      __init__.py
      wcag_en_bfsg_map.json
  core/
    __init__.py
    browser_config.py
    celery.py
    config.py
  db/
    __init__.py
    base.py
    init_db.py
    session.py
  discovery/
    __init__.py
    keywords.py
    place_resolver.py
    providers/
      __init__.py
      base.py
      google_places_provider.py
      mock_provider.py
    query_planner.py
  enrichment/
    __init__.py
    providers/
      __init__.py
      base.py
      mock_company_provider.py
  evidence/
    __init__.py
    hashing.py
    storage.py
    storage_backend.py
  models/
    company_enrichment.py
    company_qualification.py
    discovery_run.py
    lead_candidate.py
    promotion_decision.py
    website_probe.py
  services/
    company_enrichment_service.py
    company_qualification_service.py
    discovery_service.py
    promotion_service.py
    provider_execution_service.py
    website_probe_service.py
  website_probe/
    __init__.py
    providers/
      __init__.py
      base.py
      mock_provider.py
  workers/
data/
  orte_deutschland.csv
04_filter_quality.py
05_run_pipeline.py
13_city_guard.py
14_evidence_gate.py
15_run_pipeline_guarded.py
Dockerfile
docker-compose.yml
requirements.txt
.env.example
```

## Run

```bash
docker-compose up --build
```

Then open:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

The API waits for PostgreSQL and Redis to become healthy, connects with SQLAlchemy, and auto-creates the database tables on startup.

## Runtime Start Commands

Local Windows development:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

Production command (hoster-neutral):

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Frontend CORS origins for deployment:

```text
FRONTEND_ORIGINS=https://datenpflegenord.de,https://www.datenpflegenord.de,https://datenpflegenord-website.luebeck-trading.workers.dev
```

Planned API domain:

```text
https://api.datenpflegenord.de
```

Deployment examples are available in:

```text
deploy/systemd/nordaudit-api.service.example
deploy/caddy/Caddyfile.example
```

## Production VPS Betrieb

Live API domain:

```text
https://api.datenpflegenord.de
```

Service status pruefen:

```bash
sudo systemctl status nordaudit-api
```

Service neu starten:

```bash
sudo systemctl restart nordaudit-api
```

Logs anzeigen:

```bash
sudo journalctl -u nordaudit-api -f
```

Public quick-check live testen:

```bash
curl -X POST https://api.datenpflegenord.de/public/quick-check \
  -H "Content-Type: application/json" \
  -d '{"domain":"example.com"}'
```

PostgreSQL Backup manuell ausfuehren:

```bash
bash deploy/scripts/backup_postgres.sh.example
```

Backup cron example:

```text
deploy/cron/northaccessbfsg-backup.cron.example
```

Wichtig:

- `.env` niemals committen.
- Secrets (DB credentials, tokens, API keys) nur auf dem VPS in `.env` oder sicherem Secret Store halten.

## Lead Discovery Foundation

The canonical raw city data file is:

```text
data/orte_deutschland.csv
```

The file is semicolon-separated and must contain these columns:

```text
plz;stadt
```

The resolver treats this file as raw input. The `stadt` column may contain real city names as well as organizations or special postal recipients, so city resolution uses exact normalized city-name matching only. It does not use substring matching.

Supported normalization includes case-insensitive matching and German umlaut handling:

```text
Lübeck -> Luebeck -> lubeck
```

Discovery endpoints:

```bash
curl http://localhost:8000/discovery/places/Lübeck
curl http://localhost:8000/discovery/places/Luebeck
curl http://localhost:8000/discovery/places/lubeck
curl http://localhost:8000/discovery/keywords
```

Example place response:

```json
{
  "city": "Lübeck",
  "matches": [
    {
      "postal_code": "23552",
      "city": "Lübeck",
      "country": "DE"
    }
  ]
}
```

## Discovery Query Planner

A discovery run is a dry-run planning record. It resolves a city to postal codes, combines those postal codes with enabled keyword groups, and persists a deterministic query plan for a later external provider integration.

```bash
curl -X POST http://localhost:8000/discovery/runs/Lübeck
```

Example response:

```json
{
  "discovery_run_id": "<run-id>",
  "city": "Lübeck",
  "status": "done",
  "postal_codes_count": 12,
  "query_count": 336
}
```

Fetch a stored run and its candidate list:

```bash
curl http://localhost:8000/discovery/runs/{discovery_run_id}
curl http://localhost:8000/discovery/runs/{discovery_run_id}/candidates
```

## Discovery Providers

Provider adapters execute a stored query plan and persist `LeadCandidate` rows. These rows are seed candidates only. They are not confirmed BFSG applicability, accessibility findings, legal obligations, violations, or legal conclusions.

### Mock Provider

The mock provider creates bounded, deterministic test candidates with obvious test names, for example `Mock Candidate Lübeck 23552 Online Shop`.

```bash
curl -X POST http://localhost:8000/discovery/runs/{discovery_run_id}/providers/mock
curl http://localhost:8000/discovery/runs/{discovery_run_id}/candidates
```

Example provider response:

```json
{
  "discovery_run_id": "<run-id>",
  "provider": "mock",
  "candidates_created": 10,
  "candidates_total": 10
}
```

### Google Places API Provider

The Google Places API provider is disabled by default. Tests do not call Google, and normal local runs do not require an API key.

Required environment settings for live use:

```text
GOOGLE_PLACES_ENABLED=false
GOOGLE_PLACES_API_KEY=
GOOGLE_PLACES_TIMEOUT_SECONDS=10
GOOGLE_PLACES_MAX_RESULTS_PER_QUERY=5
```

Endpoint:

```bash
curl -X POST http://localhost:8000/discovery/runs/{discovery_run_id}/providers/google-places
```

If disabled or missing configuration, the endpoint returns a clear error and does not make an external call. If enabled with a key, Places API responses are mapped into raw `LeadCandidate` seed rows with `source="google_places"`.

Google Places API results are only seed candidates. Northdata-style or comparable company enrichment is required before any candidate can be treated as qualified for downstream audit consideration.

## Company Enrichment Foundation

`CompanyEnrichment` stores company-data signals for a `LeadCandidate`: legal form, registry ID, source URL, employee count, annual revenue, balance sheet total, raw source payload, and confidence. These records are evidence/signal data only. They do not make legal conclusions or final BFSG applicability decisions.

The mock enrichment provider creates deterministic test data only. It does not call Northdata, scrape company registers, scrape websites, or claim real company data.

```bash
curl -X POST http://localhost:8000/discovery/candidates/{candidate_id}/enrichment/mock
curl http://localhost:8000/discovery/candidates/{candidate_id}/enrichment
```

Example response:

```json
{
  "candidate_id": "<candidate-id>",
  "enrichment_id": "<enrichment-id>",
  "source": "mock_company_data",
  "confidence_score": 0.5
}
```

A future Northdata or company-register integration should live behind the enrichment provider abstraction. Live company-data calls are not implemented in this foundation step.

## Company Qualification Precheck

`CompanyQualification` stores precheck signals for a `LeadCandidate`. It is a signal and review layer only. It does not make legal conclusions and it does not call Northdata or any external company-data provider yet.

Precheck endpoints:

```bash
curl -X POST http://localhost:8000/discovery/candidates/{candidate_id}/qualification/precheck
curl http://localhost:8000/discovery/candidates/{candidate_id}/qualification
```

The precheck uses the latest `CompanyEnrichment` when available. Missing company data results in `needs_company_data` or `needs_human_review`. Microenterprise-like data can signal `likely_not_applicable` or review need. Non-microenterprise-like data can signal `possible_bfsg_candidate` only when category/B2C and website signals are present. These are review signals, not legal scoring or final applicability decisions.

Configured microenterprise signal thresholds:

```text
BFSG_MICROENTERPRISE_EMPLOYEE_THRESHOLD=10
BFSG_MICROENTERPRISE_REVENUE_THRESHOLD_EUR=2000000
BFSG_MICROENTERPRISE_BALANCE_THRESHOLD_EUR=2000000
```

These thresholds are only used as precheck signals.

## Promotion Gate

`PromotionDecision` stores an internal routing decision for a `LeadCandidate` after company enrichment and qualification precheck. The possible routing statuses are:

```text
rejected
needs_review
ready_for_website_probe
```

Promotion endpoints:

```bash
curl -X POST http://localhost:8000/discovery/candidates/{candidate_id}/promotion/evaluate
curl http://localhost:8000/discovery/candidates/{candidate_id}/promotion
```

Example response:

```json
{
  "candidate_id": "<candidate-id>",
  "promotion_decision_id": "<decision-id>",
  "status": "needs_review",
  "reason_code": "mock_or_test_data",
  "confidence_score": 0.2
}
```

The Promotion Gate is only internal routing. `ready_for_website_probe` means the candidate can move to a Website Probe stage. It does not mean a BFSG obligation, an accessibility issue, or any violation has been established.

## Website Probe Foundation

`WebsiteProbe` stores lightweight website and web-flow signals for a promoted `LeadCandidate`. It is not a full accessibility audit, not Playwright scanning, not legal scoring, and not report generation.

Mock Website Probe endpoints:

```bash
curl -X POST http://localhost:8000/discovery/candidates/{candidate_id}/website-probe/mock
curl http://localhost:8000/discovery/candidates/{candidate_id}/website-probe
```

Example response:

```json
{
  "candidate_id": "<candidate-id>",
  "website_probe_id": "<probe-id>",
  "status": "skipped",
  "confidence_score": 0.2
}
```

The mock website probe does not fetch websites or scrape pages. It derives deterministic test signals from the candidate domain, category, and raw data. A candidate without a domain is skipped with `missing_domain` evidence. Ecommerce-like candidates can produce shop, checkout, and B2C transaction signals; booking and transport candidates can produce booking/ticket-like signals; banking candidates can produce login-like signals.

### Live HTTP Website Probe

The live HTTP website probe is disabled by default. When explicitly enabled, it performs one lightweight HTTP GET for a candidate domain and stores reachability and page-level signal fields. It does not crawl multiple pages, submit forms, use Playwright, run an accessibility audit, generate a report, bypass robots or security protections, or make legal conclusions.

Endpoint:

```bash
curl -X POST http://localhost:8000/discovery/candidates/{candidate_id}/website-probe/live
```

Configuration:

```text
WEBSITE_PROBE_LIVE_ENABLED=false
WEBSITE_PROBE_TIMEOUT_SECONDS=10
WEBSITE_PROBE_USER_AGENT=NorthAccessBFSGBot/0.1
WEBSITE_PROBE_MAX_BODY_BYTES=200000
```

If disabled, the endpoint returns a clear service-unavailable error and does not make a network call. If enabled and the candidate has no domain or website-like raw data value, the probe stores a skipped `missing_domain` result. If enabled and a domain is present, the provider normalizes it to an HTTPS URL when no scheme is supplied, requests only that URL, caps the response body, and derives lightweight signals such as homepage, impressum, login, shop, booking, checkout/cart, and B2C transaction indicators.

These signals only help decide whether a future full scan may be worth scheduling. They are not accessibility results, legal conclusions, or BFSG violation findings. A full scan/audit stage comes later.

This discovery layer does not scrape websites, does not perform reporting, and does not run accessibility scans for seed candidates automatically.

## Public Quick Check

`POST /public/quick-check` provides a lightweight technical pre-check for one URL/domain input.

Request body:

```json
{ "url": "https://example.com" }
```

or

```json
{ "domain": "example.com" }
```

The endpoint normalizes domains to HTTPS URLs, performs one HTTP fetch, captures final URL, and returns checks for reachability, HTTPS, title, meta description, H1, HTML lang, impressum link, privacy link, and basic tracker-domain signals.

Public quick check requests are rate-limited per client IP to reduce abuse.

Configuration:

```text
QUICK_CHECK_RATE_LIMIT_PER_MINUTE=10
```

If the limit is exceeded, the endpoint returns HTTP `429` with:

```json
{
  "detail": "Zu viele Schnellcheck-Anfragen. Bitte versuchen Sie es später erneut."
}
```

The response is technical only and includes this disclaimer:

```text
Diese automatisierte Vorprüfung liefert technische Hinweise und ersetzt keine vollständige manuelle Barrierefreiheitsprüfung, keine Rechtsberatung und keine behördliche Zertifizierung.
```

## Scan Readiness Gate

`ScanReadinessDecision` stores the internal routing decision between Website Probe and future scan execution. It combines the latest `PromotionDecision` and `WebsiteProbe` for a `LeadCandidate` and can return:

```text
rejected
needs_review
ready_for_scan
```

Scan readiness endpoints:

```bash
curl -X POST http://localhost:8000/discovery/candidates/{candidate_id}/scan-readiness/evaluate
curl http://localhost:8000/discovery/candidates/{candidate_id}/scan-readiness
curl -X POST http://localhost:8000/discovery/candidates/{candidate_id}/scans
```

The scan skeleton endpoint creates a `pending` `Scan` only when the latest scan readiness decision is `ready_for_scan`. It does not enqueue Celery, launch Playwright, run axe, crawl websites, generate reports, or make legal conclusions. If the candidate is not ready for scan, the endpoint returns a clear conflict response.

## Browser Smoke Probe

The browser smoke probe is a minimal execution foundation for an existing `Scan`. It opens exactly one URL with Playwright, captures lightweight page metadata, stores a `ScanEvidence` record, and marks the scan `done` or `failed`.

Endpoint:

```bash
curl -X POST http://localhost:8000/scans/{scan_id}/browser-smoke
```

Captured metadata:

```text
final_url
page_title
http_status
timestamp
```

This stage is not a full accessibility audit. It does not run axe, crawl additional pages, submit forms, generate reports, create letters, or make legal conclusions.

## Axe Homepage Audit

The axe homepage audit runs axe on exactly one homepage URL for an existing `Scan`. It stores `Finding` rows for axe findings and an `axe_homepage` `ScanEvidence` record with technical metadata.

Endpoint:

```bash
curl -X POST http://localhost:8000/scans/{scan_id}/axe-homepage
```

This stage is one-page only. It does not crawl, run multi-page journeys, generate reports, create PDFs, create letters, or make legal conclusions. Findings are technical signals for review, not legal conclusions.

## Finding Compliance Mapping

Compliance mapping connects stored axe `Finding` rows to deterministic WCAG, EN 301 549, and BFSG signal references. The mapping stores technical references in `compliance_mappings` and keeps the original `findings` rows unchanged.

Endpoints:

```bash
curl -X POST http://localhost:8000/findings/{finding_id}/compliance/map
curl http://localhost:8000/findings/{finding_id}/compliance
curl -X POST http://localhost:8000/scans/{scan_id}/compliance/map
```

Known axe rule IDs map to predefined reference lists. Unknown axe rule IDs map to empty reference lists with `review_required=true` and low confidence.

These mappings are technical references and review signals only. They are not legal advice, certification, reports, PDFs, letters, or final applicability decisions.

## Review Queue Foundation

The review queue stores human review work items for technical signals that need a person to inspect them. It can track findings, compliance mappings, candidates, and website probes.

Endpoints:

```bash
curl http://localhost:8000/review/items
curl "http://localhost:8000/review/items?status=pending&subject_type=finding"
curl http://localhost:8000/review/items/{review_item_id}
curl -X POST http://localhost:8000/review/items
curl -X PATCH http://localhost:8000/review/items/{review_item_id}
```

Review items are created automatically for compliance mappings with `review_required=true`, pending high or critical findings, and website probes with `needs_review` status.

This is a human review workflow only. It is not legal advice, certification, reporting, PDF generation, letters, or a final applicability decision. It does not decide legal obligation; it only routes technical and compliance reference signals for manual review.

## Report JSON Foundation

The JSON report endpoint generates a machine-readable snapshot for one scan. It includes scan metadata, technical findings, compliance reference mappings, review queue items, summary counts, and an evidence manifest.

Endpoints:

```bash
curl -X POST http://localhost:8000/scans/{scan_id}/reports/json
curl http://localhost:8000/reports/{report_id}
curl http://localhost:8000/scans/{scan_id}/reports
```

Report output also includes:

- `evidence_quality` (quality snapshot for scan evidence)
- `review_summary` (human review status summary)
- finding-level `review_outcome` (`approved`, `rejected`, `pending`)
- finding-level `excluded_from_final_summary` when review outcome is `rejected`

Rejected findings are not deleted. They remain in raw report output and are marked for summary exclusion only.

This is JSON only. It is not a PDF, letter, legal advice, certification, or final applicability decision.

## Journey Scan Foundation

Journey planning creates deterministic planned journey rows for a scan from existing domain and website-probe signals. It does not crawl pages, run Playwright, submit forms, or automate checkout.

Endpoints:

```bash
curl -X POST http://localhost:8000/scans/{scan_id}/journeys/plan
curl http://localhost:8000/scans/{scan_id}/journeys
```

The planner always creates a homepage journey when a URL or domain is available. Shop, cart, checkout, booking, and login journeys are planned when matching website-probe signals exist. Search and contact-form journeys remain skipped placeholders until signals are available.

Journeys are planned technical signals only. They are not legal conclusions, reports, PDFs, letters, or full journey automation.

## Journey Execution And Axe

Journey execution opens exactly one planned journey URL and stores lightweight browser metadata as `journey_smoke` evidence. Axe per journey opens exactly one journey URL, stores `axe_journey` evidence, and creates technical `Finding` rows linked with `journey_id`.

Endpoints:

```bash
curl -X POST http://localhost:8000/journeys/{journey_id}/execute-smoke
curl -X POST http://localhost:8000/scans/{scan_id}/journeys/execute-smoke
curl -X POST http://localhost:8000/journeys/{journey_id}/axe
curl -X POST http://localhost:8000/scans/{scan_id}/journeys/axe
```

This is minimal one-URL execution only. It does not crawl, submit forms, automate checkout, generate PDFs, create letters, provide legal advice, or certify anything.

## Evidence Manifest Hardening

Evidence manifests expose evidence rows with scan ID, related entity fields when present, storage key/path, metadata, hash when already present, and creation time. They also include:

- `evidence_count`
- `missing_hash_count`
- `missing_related_entity_count`
- `evidence_types` counts
- `related_entity_types` counts

Scan evidence quality endpoint:

```bash
curl http://localhost:8000/scans/{scan_id}/evidence/quality
```

The quality result reports whether evidence is `insufficient`, `partial`, or `usable` based on available technical evidence signals.

Review summary endpoint:

```bash
curl http://localhost:8000/scans/{scan_id}/review/summary
```

The review summary reports pending/approved/rejected/needs-more-info counts and whether blocking review items remain.

These summaries are workflow signals only. They are not legal certification or legal conclusions.

## Delta Comparison Foundation

Delta comparison compares technical findings from a baseline scan against a target scan. It uses deterministic finding fingerprints to group matching findings without relying on database IDs or timestamps.

Endpoints:

```bash
curl -X POST http://localhost:8000/scans/{target_scan_id}/delta/{baseline_scan_id}
curl http://localhost:8000/delta/{comparison_id}
curl http://localhost:8000/scans/{scan_id}/delta
```

The output groups findings as `new_findings`, `resolved_findings`, and `unchanged_findings`, with compact evidence and summary counts. This is a technical comparison only. It is not legal advice, certification, reports, PDFs, letters, or a final applicability decision.

## Validation

GitHub Actions runs the same validation on pull requests and pushes to `main`. The CI workflow does not require Docker, external API keys, Google Places, or browser installation.

Local Linux/macOS:

```bash
python -m py_compile \
  04_filter_quality.py \
  05_run_pipeline.py \
  13_city_guard.py \
  14_evidence_gate.py \
  15_run_pipeline_guarded.py

python 15_run_pipeline_guarded.py
python -m pytest -q
```

Windows PowerShell:

```powershell
python -m py_compile `
  04_filter_quality.py `
  05_run_pipeline.py `
  13_city_guard.py `
  14_evidence_gate.py `
  15_run_pipeline_guarded.py

python 15_run_pipeline_guarded.py
python -m pytest -q
```

Make targets are available on systems with `make`:

```bash
make validate
make test
make pipeline
```

The numbered guarded pipeline files validate that runtime dependencies are present and that the canonical city CSV is usable.
The guarded runner fails if `data/orte_deutschland.csv` is missing, unreadable, missing required columns, header-only, or contains zero usable rows.

## Async Scan Flow

Create a lead directly in the database while a public lead API does not exist yet:

```bash
docker-compose exec db psql -U northaccess -d northaccessbfsg -c "INSERT INTO leads (id, domain, company_name) VALUES ('11111111-1111-1111-1111-111111111111', 'https://example.com', 'Example') ON CONFLICT (id) DO NOTHING;"
```

Run a scan for the lead:

```bash
curl -X POST http://localhost:8000/scans/run/11111111-1111-1111-1111-111111111111
```

Expected immediate response:

```json
{"scan_id":"<scan-id>"}
```

The API creates a `pending` scan and queues a Celery task without blocking. The worker launches Playwright headless Chromium, loads the lead domain, runs axe-core, captures evidence metadata, and persists raw findings.

Lifecycle:

```text
pending -> running -> processing -> done
```

If task execution fails, the worker marks the scan as `failed` and stores `error_message`.

## Compliance Mapping Flow

Run deterministic compliance mapping for a completed scan:

```bash
curl -X POST http://localhost:8000/compliance/run/{scan_id}
```

Compliance results are stored separately in `compliance_findings`. Raw `findings` rows are never overwritten. Re-running the endpoint updates the same `finding_id` + `mapping_version` compliance rows and removes stale rows for that scan/version.

For finding-level reference mapping, use:

```bash
curl -X POST http://localhost:8000/findings/{finding_id}/compliance/map
curl http://localhost:8000/findings/{finding_id}/compliance
curl -X POST http://localhost:8000/scans/{scan_id}/compliance/map
```

Finding-level mappings are stored in `compliance_mappings` as technical WCAG, EN 301 549, and BFSG signal references only. They are not legal advice, certification, reports, PDFs, letters, or final applicability decisions.

## Browser Configuration

The worker defaults to Chromium and also installs Firefox:

```text
BROWSER_NAME=chromium
BROWSER_HEADLESS=true
BROWSER_NAVIGATION_TIMEOUT_MS=30000
BROWSER_ACTION_TIMEOUT_MS=10000
BROWSER_VIEWPORT_WIDTH=1440
BROWSER_VIEWPORT_HEIGHT=900
BROWSER_RETRIES=1
BROWSER_WAIT_UNTIL=networkidle
```

WebKit is supported by configuration but is not installed in the default image.
