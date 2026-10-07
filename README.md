# Bulk Certificate Generator

A FastAPI service that accepts one request for many recipients, generates a PDF certificate for each valid recipient, and reports successes and failures per recipient.

## Setup

Requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

On Windows, activate the environment with `.venv\Scripts\activate`.

## Run

```bash
uvicorn app.main:app --reload
```

The interactive API docs are at `http://127.0.0.1:8000/docs`. `GET /health` returns `{"status":"ok"}`.

## Create a job

```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "event_title": "Python Workshop",
    "completion_date": "2026-10-07",
    "recipients": [
      {"name": "Ada Lovelace"},
      {"name": "Grace Hopper"},
      {"name": ""}
    ]
  }'
```

The `202 Accepted` response has a `job_id`, `status`, and `status_url`. Send between 1 and 1,000 recipients. The title and each name must contain 1 to 200 non-whitespace characters after trimming. The date uses ISO `YYYY-MM-DD` format. Malformed job-level fields return `422`; invalid recipient entries are kept as failed rows so valid entries can still run. Recipient positions are zero-based and preserve request order.

## Check progress and download PDFs

```bash
curl http://127.0.0.1:8000/jobs/JOB_ID
curl -OJ http://127.0.0.1:8000/jobs/JOB_ID/certificates/RECIPIENT_ID
```

The job response includes `total`, `pending`, `succeeded`, and `failed` counts, plus each recipient's ID, position, name, status, error, and `certificate_url` when successful. Jobs move from `queued` to `running`, then `completed`, `completed_with_errors`, or `failed`. A failed job has no successful PDFs. Unknown jobs and unavailable certificates return `404`.

## Run tests

```bash
pytest
```

Tests cover request validation, job creation, progress, PDF output, a generation failure followed by another successful recipient, and retrieval.

## Design decisions

- SQLite stores job and recipient status. Separate connections keep the worker independent from the request. `DATABASE_PATH` changes the default `data/jobs.sqlite3` location.
- ReportLab draws one fixed landscape A4 certificate. Files are stored under `data/certificates/JOB_ID/RECIPIENT_ID.pdf`; `CERTIFICATE_DIR` changes that root. ID-based filenames avoid using recipient input as a path.
- FastAPI submits each job to an in-process pool with two workers after accepting the request. The worker handles recipients independently, commits each result, and writes PDFs to a temporary file before renaming them to their final names. This allows status polling while the job runs, limits concurrent jobs, and prevents a failed PDF write from being served as complete.
- Workers run in this server process. A server crash can leave a job `queued` or `running`, and jobs are not automatically retried. A durable task queue and shared file storage would be the next step for deployment across multiple server processes.
