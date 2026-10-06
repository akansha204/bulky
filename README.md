# Bulk Certificate Generator

FastAPI project scaffold for a bulk PDF certificate generation API. Certificate jobs, storage, and download endpoints are the next implementation step.

## Setup

Requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

On Windows, activate the environment with `.venv\\Scripts\\activate`.

## Run

```bash
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation. The scaffold currently provides `GET /health`.

## Test

```bash
pytest
```

## Planned design

The implementation will use SQLite for job and recipient records, ReportLab for one fixed PDF template, and local `data/` storage for generated certificates. FastAPI background tasks will process each recipient independently. This keeps the assignment easy to run locally; in-process jobs will not survive a server crash without additional recovery logic.
