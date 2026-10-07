"""Small SQLite repository for jobs and their recipient results."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(db_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                event_title TEXT NOT NULL,
                completion_date TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recipients (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL REFERENCES jobs(id),
                position INTEGER NOT NULL,
                name TEXT,
                status TEXT NOT NULL,
                error TEXT,
                file_path TEXT,
                UNIQUE(job_id, position)
            );
            CREATE INDEX IF NOT EXISTS idx_recipients_job ON recipients(job_id);
        """)


def get_job(db_path: Path, job_id: str) -> dict | None:
    with connect(db_path) as db:
        job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None:
            return None
        rows = db.execute(
            "SELECT id, position, name, status, error, file_path FROM recipients WHERE job_id = ? ORDER BY position",
            (job_id,),
        ).fetchall()

    recipients = [
        {
            "id": row["id"],
            "position": row["position"],
            "name": row["name"],
            "status": row["status"],
            "error": row["error"],
            "certificate_url": (
                f"/jobs/{job_id}/certificates/{row['id']}"
                if row["status"] == "succeeded" and row["file_path"] else None
            ),
        }
        for row in rows
    ]
    return {
        "id": job["id"],
        "event_title": job["event_title"],
        "completion_date": job["completion_date"],
        "status": job["status"],
        "created_at": job["created_at"],
        "total": len(recipients),
        "pending": sum(row["status"] == "pending" for row in recipients),
        "succeeded": sum(row["status"] == "succeeded" for row in recipients),
        "failed": sum(row["status"] == "failed" for row in recipients),
        "recipients": recipients,
    }
