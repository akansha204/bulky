import uuid
from datetime import date

import pytest
from pydantic import ValidationError

from app.database import connect, get_job, init_db
from app.schemas import JobInput, RecipientInput


def test_request_schema_validates_shared_fields_and_recipient_limit() -> None:
    payload = JobInput.model_validate({
        "event_title": "  Workshop  ",
        "completion_date": "2026-10-07",
        "recipients": [{"name": "Ada"}],
    })
    assert payload.event_title == "Workshop"
    assert payload.completion_date == date(2026, 10, 7)

    with pytest.raises(ValidationError):
        JobInput.model_validate({"event_title": "Workshop", "completion_date": "2026-10-07", "recipients": []})
    with pytest.raises(ValidationError):
        JobInput.model_validate({"event_title": "Workshop", "completion_date": "2026-10-07", "recipients": [{}] * 1001})
    with pytest.raises(ValidationError):
        RecipientInput.model_validate({"name": "   "})


def test_sqlite_job_status_is_derived_from_recipient_rows(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    init_db(db_path)
    job_id, recipient_id = str(uuid.uuid4()), str(uuid.uuid4())
    with connect(db_path) as db:
        db.execute("INSERT INTO jobs VALUES (?, ?, ?, ?, ?)", (job_id, "Workshop", "2026-10-07", "running", "now"))
        db.execute(
            "INSERT INTO recipients (id, job_id, position, name, status, file_path) VALUES (?, ?, ?, ?, ?, ?)",
            (recipient_id, job_id, 0, "Ada", "succeeded", "/tmp/ada.pdf"),
        )

    job = get_job(db_path, job_id)
    assert job is not None
    assert job["total"] == job["succeeded"] == 1
    assert job["recipients"][0]["certificate_url"] == f"/jobs/{job_id}/certificates/{recipient_id}"
