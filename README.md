# NorthAccessBFSG

NorthAccessBFSG is a FastAPI backend foundation for a BFSG/WCAG compliance audit platform.

The current scope includes backend infrastructure, asynchronous scans, raw accessibility findings, compliance mapping basics, evidence bundle storage, and a minimal Lead Discovery foundation for city, keyword, provider seed, company enrichment, and company precheck workflows.

## Project Structure

```text
app/
  __init__.py
  main.py
  api/
    __init__.py
    compliance.py
    discovery.py
    evidence.py
    health.py
    scans.py
  compliance/
    __init__.py
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
  services/
    company_enrichment_service.py
    company_qualification_service.py
    discovery_service.py
    provider_execution_service.py
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

This discovery layer does not scrape websites, does not perform reporting, and does not run accessibility scans for seed candidates automatically.

## Guarded Pipeline

The numbered guarded pipeline files validate that runtime dependencies are present and that the canonical city CSV is usable:

```bash
python -m py_compile \
  04_filter_quality.py \
  05_run_pipeline.py \
  13_city_guard.py \
  14_evidence_gate.py \
  15_run_pipeline_guarded.py

python 15_run_pipeline_guarded.py
```

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
