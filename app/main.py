"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(title="Bulk Certificate Generator", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
