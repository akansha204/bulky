import asyncio
import io
import threading
from pathlib import Path

import httpx
from pypdf import PdfReader

from app.main import create_app
from app.certificates import generate_certificate


def client(tmp_path: Path, generator=generate_certificate) -> httpx.AsyncClient:
    app = create_app(tmp_path / "jobs.sqlite3", tmp_path / "certificates", generator)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def wait_for_job(api: httpx.AsyncClient, status_url: str) -> dict:
    for _ in range(200):
        job = (await api.get(status_url)).json()
        if job["status"] in {"completed", "completed_with_errors", "failed"}:
            return job
        await asyncio.sleep(0.01)
    raise AssertionError("Job did not finish")


def test_create_job_records_valid_and_invalid_recipients(tmp_path: Path) -> None:
    async def request() -> tuple[httpx.Response, dict]:
        async with client(tmp_path) as api:
            response = await api.post("/jobs", json={
                "event_title": "Python Course",
                "completion_date": "2026-10-07",
                "recipients": [{"name": " Ada Lovelace "}, {"name": "   "}, {"name": "Grace Hopper"}],
            })
            job = await wait_for_job(api, response.json()["status_url"])
            return response, job

    response, job = asyncio.run(request())
    assert response.status_code == 202
    assert job["total"] == 3
    assert job["pending"] == 0
    assert job["succeeded"] == 2
    assert job["failed"] == 1
    assert job["status"] == "completed_with_errors"
    assert job["recipients"][0]["name"] == "Ada Lovelace"
    assert job["recipients"][1]["error"]
    assert [row["position"] for row in job["recipients"]] == [0, 1, 2]


def test_invalid_job_request_and_unknown_job(tmp_path: Path) -> None:
    async def request() -> tuple[httpx.Response, httpx.Response]:
        async with client(tmp_path) as api:
            response = await api.post("/jobs", json={
                "event_title": " ", "completion_date": "bad", "recipients": [],
            })
            missing = await api.get("/jobs/unknown")
            return response, missing

    response, missing = asyncio.run(request())
    assert response.status_code == 422
    assert missing.status_code == 404


def test_recipient_limit_rejects_oversized_job(tmp_path: Path) -> None:
    async def request() -> httpx.Response:
        async with client(tmp_path) as api:
            return await api.post("/jobs", json={
                "event_title": "Workshop", "completion_date": "2026-10-07",
                "recipients": [{"name": "Participant"}] * 1001,
            })

    assert asyncio.run(request()).status_code == 422


def test_all_valid_recipients_complete(tmp_path: Path) -> None:
    async def request() -> dict:
        async with client(tmp_path) as api:
            response = await api.post("/jobs", json={
                "event_title": "Workshop", "completion_date": "2026-10-07",
                "recipients": [{"name": "Ada"}, {"name": "Grace"}],
            })
            return await wait_for_job(api, response.json()["status_url"])

    job = asyncio.run(request())
    assert job["status"] == "completed"
    assert job["succeeded"] == 2
    assert job["failed"] == 0
    assert all(row["certificate_url"] for row in job["recipients"])


def test_all_invalid_recipients_fail_without_pdf(tmp_path: Path) -> None:
    async def request() -> dict:
        async with client(tmp_path) as api:
            response = await api.post("/jobs", json={
                "event_title": "Workshop", "completion_date": "2026-10-07",
                "recipients": [{"name": " "}, {"name": 123}, "bad row"],
            })
            return await wait_for_job(api, response.json()["status_url"])

    job = asyncio.run(request())
    assert job["status"] == "failed"
    assert job["failed"] == 3
    assert job["pending"] == job["succeeded"] == 0
    assert all(row["certificate_url"] is None for row in job["recipients"])


def test_progress_and_individual_generation_failure(tmp_path: Path) -> None:
    entered = threading.Event()
    release = threading.Event()

    def generator(path: Path, name: str, title: str, completed) -> None:
        if name == "First":
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test timed out")
        if name == "Second":
            raise RuntimeError("printer unavailable")
        generate_certificate(path, name, title, completed)

    async def request() -> tuple[dict, dict]:
        async with client(tmp_path, generator) as api:
            response = await api.post("/jobs", json={
                "event_title": "Workshop", "completion_date": "2026-10-07",
                "recipients": [{"name": "First"}, {"name": "Second"}, {"name": "Third"}],
            })
            url = response.json()["status_url"]
            for _ in range(200):
                if entered.is_set():
                    break
                await asyncio.sleep(0.01)
            assert entered.is_set()
            running = (await api.get(url)).json()
            release.set()
            finished = await wait_for_job(api, url)
            return running, finished

    running, finished = asyncio.run(request())
    assert running["status"] == "running"
    assert running["pending"] == 3
    assert finished["status"] == "completed_with_errors"
    assert finished["succeeded"] == 2
    assert finished["failed"] == 1
    assert "printer unavailable" in finished["recipients"][1]["error"]
    assert finished["recipients"][2]["status"] == "succeeded"


def test_download_generated_certificate(tmp_path: Path) -> None:
    async def request() -> tuple[dict, httpx.Response, httpx.Response]:
        async with client(tmp_path) as api:
            response = await api.post("/jobs", json={
                "event_title": "Python Course", "completion_date": "2026-10-07",
                "recipients": [{"name": "Ada Lovelace"}, {"name": " "}],
            })
            job = await wait_for_job(api, response.json()["status_url"])
            base = f"/jobs/{job['id']}/certificates/"
            pdf = await api.get(job["recipients"][0]["certificate_url"])
            missing = await api.get(base + job["recipients"][1]["id"])
            return job, pdf, missing

    job, pdf, missing = asyncio.run(request())
    assert job["status"] == "completed_with_errors"
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-")
    text = PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
    assert "Ada Lovelace" in text
    assert "Python Course" in text
    assert "October 07, 2026" in text
    assert missing.status_code == 404
