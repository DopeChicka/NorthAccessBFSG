# NorthAccessBFSG

NorthAccessBFSG is a FastAPI backend foundation for a BFSG/WCAG compliance audit platform.

The current scope includes backend infrastructure, asynchronous scans, raw accessibility findings, compliance mapping basics, evidence bundle storage, and a minimal Lead Discovery foundation for city and keyword resolution.

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
  evidence/
    __init__.py
    hashing.py
    storage.py
    storage_backend.py
  models/
  services/
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

This is only the resolver and keyword foundation for later lead discovery. It is not a live Google Maps API integration. It does not scrape websites and does not call external discovery providers.

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
