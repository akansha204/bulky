"""Process a bulk job without letting one recipient stop the rest."""

import os
from datetime import date
from pathlib import Path
from typing import Callable

from app.certificates import generate_certificate
from app.database import connect

Generator = Callable[[Path, str, str, date], None]


def process_job(db_path: Path, certificate_dir: Path, job_id: str, generator: Generator = generate_certificate) -> None:
    with connect(db_path) as db:
        job = db.execute("SELECT event_title, completion_date FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None:
            return
        db.execute("UPDATE jobs SET status = 'running' WHERE id = ?", (job_id,))
        recipients = db.execute(
            "SELECT id, name FROM recipients WHERE job_id = ? AND status = 'pending' ORDER BY position",
            (job_id,),
        ).fetchall()

    for recipient in recipients:
        destination = certificate_dir / job_id / f"{recipient['id']}.pdf"
        temporary = destination.with_suffix(".pdf.tmp")
        try:
            generator(temporary, recipient["name"], job["event_title"], date.fromisoformat(job["completion_date"]))
            os.replace(temporary, destination)
            with connect(db_path) as db:
                db.execute(
                    "UPDATE recipients SET status = 'succeeded', error = NULL, file_path = ? WHERE id = ?",
                    (str(destination), recipient["id"]),
                )
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            with connect(db_path) as db:
                db.execute(
                    "UPDATE recipients SET status = 'failed', error = ? WHERE id = ?",
                    (f"Generation failed: {exc}", recipient["id"]),
                )

    with connect(db_path) as db:
        successful = db.execute(
            "SELECT COUNT(*) FROM recipients WHERE job_id = ? AND status = 'succeeded'", (job_id,)
        ).fetchone()[0]
        failed = db.execute(
            "SELECT COUNT(*) FROM recipients WHERE job_id = ? AND status = 'failed'", (job_id,)
        ).fetchone()[0]
        status = "completed_with_errors" if successful and failed else "completed" if successful else "failed"
        db.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
