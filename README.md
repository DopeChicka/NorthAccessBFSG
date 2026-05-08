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
  core/
    __init__.py
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

The API waits for PostgreSQL to become healthy, connects with SQLAlchemy, and auto-creates the `leads`, `scans`, and `findings` tables on startup.
