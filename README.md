# NorthAccessBFSG

Minimal FastAPI backend foundation for a BFSG/WCAG compliance audit platform.

## Project Structure

```text
app/
  __init__.py
  main.py
  api/
    __init__.py
    health.py
    scans.py
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
  models/
    __init__.py
    finding.py
    lead.py
    scan.py
  services/
    __init__.py
    scan_service.py
  workers/
    __init__.py
    playwright_engine.py
    scan_worker.py
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

```text
http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

The API waits for PostgreSQL and Redis to become healthy, connects with SQLAlchemy, and auto-creates the `leads`, `scans`, and `findings` tables on startup.

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

Inspect scan status and evidence metadata:

```bash
docker-compose exec db psql -U northaccess -d northaccessbfsg -c "SELECT id, status, error_message, evidence_metadata->>'current_url' AS current_url FROM scans;"
```

Inspect stored findings:

```bash
docker-compose exec db psql -U northaccess -d northaccessbfsg -c "SELECT rule_id, severity, wcag_refs, confidence_score FROM findings;"
```

The worker process can also be started independently:

```bash
celery -A app.core.celery worker --loglevel=info
```

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
