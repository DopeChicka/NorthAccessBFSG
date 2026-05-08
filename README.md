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

Run a scan for an existing lead:

```bash
curl -X POST http://localhost:8000/scans/run/{lead_id}
```

Expected immediate response:

```json
{"scan_id":"<scan-id>"}
```

The API creates a `pending` scan and queues a Celery task without blocking. The worker then updates the scan lifecycle:

```text
pending -> running -> done
```

If task execution fails, the worker marks the scan as `failed`.

The worker process can also be started independently:

```bash
celery -A app.core.celery worker --loglevel=info
```
