"""FastAPI application entry point."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import ValidationError

from app.database import connect, get_job, init_db
from app.schemas import JobInput, RecipientInput
from app.worker import Generator, process_job
from app.certificates import generate_certificate


def create_app(
    db_path: Path | None = None,
    certificate_dir: Path | None = None,
    generator: Generator = generate_certificate,
) -> FastAPI:
    db_path = (db_path or Path(os.getenv("DATABASE_PATH", "data/jobs.sqlite3"))).resolve()
    certificate_dir = (certificate_dir or Path(os.getenv("CERTIFICATE_DIR", "data/certificates"))).resolve()
    init_db(db_path)
    certificate_dir.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="Bulk Certificate Generator", version="0.1.0")
    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="certificate-job")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    async def start_worker(job_id: str) -> None:
        executor.submit(process_job, db_path, certificate_dir, job_id, generator)

    @app.post("/jobs", status_code=202)
    async def create_job(payload: JobInput, background_tasks: BackgroundTasks) -> dict[str, str]:
        job_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        with connect(db_path) as db:
            db.execute(
                "INSERT INTO jobs VALUES (?, ?, ?, ?, ?)",
                (job_id, payload.event_title, payload.completion_date.isoformat(), "queued", created_at),
            )
            for position, raw in enumerate(payload.recipients):
                try:
                    recipient = RecipientInput.model_validate(raw)
                    name, status, error = recipient.name, "pending", None
                except ValidationError as exc:
                    name = raw["name"][:200] if isinstance(raw, dict) and isinstance(raw.get("name"), str) else None
                    status, error = "failed", exc.errors()[0]["msg"]
                db.execute(
                    "INSERT INTO recipients (id, job_id, position, name, status, error) VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), job_id, position, name, status, error),
                )
        background_tasks.add_task(start_worker, job_id)
        return {"job_id": job_id, "status": "queued", "status_url": f"/jobs/{job_id}"}

    @app.get("/jobs/{job_id}")
    async def job_status(job_id: str) -> dict:
        job = get_job(db_path, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @app.get("/jobs/{job_id}/certificates/{recipient_id}")
    async def download_certificate(job_id: str, recipient_id: str) -> Response:
        with connect(db_path) as db:
            row = db.execute(
                "SELECT status, file_path FROM recipients WHERE job_id = ? AND id = ?",
                (job_id, recipient_id),
            ).fetchone()
        if row is None or row["status"] != "succeeded" or not row["file_path"]:
            raise HTTPException(status_code=404, detail="Certificate not found")
        path = Path(row["file_path"])
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Certificate file not found")
        return Response(
            content=path.read_bytes(),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="certificate-{recipient_id}.pdf"'},
        )

    return app


app = create_app()
