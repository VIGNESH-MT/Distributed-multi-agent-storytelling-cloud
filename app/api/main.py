from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.api.routes.stories import router as stories_router

APP_VERSION = "0.1.2"
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


class HealthResponse(BaseModel):
    status: str
    service: str


class HealthCheckResponse(HealthResponse):
    version: str


app = FastAPI(
    title="Distributed Multi-Agent Storytelling Cloud",
    description=(
        "A consistency-aware distributed multi-agent storytelling "
        "system deployed on a private Kubernetes cloud."
    ),
    version=APP_VERSION,
)

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", response_model=HealthCheckResponse)
def health_check() -> HealthCheckResponse:
    return HealthCheckResponse(
        status="healthy",
        service="storytelling-api",
        version=APP_VERSION,
    )


@app.get("/health/live", response_model=HealthResponse)
def liveness_check() -> HealthResponse:
    return HealthResponse(
        status="alive",
        service="storytelling-api",
    )


@app.get("/health/ready", response_model=HealthResponse)
def readiness_check() -> HealthResponse:
    return HealthResponse(
        status="ready",
        service="storytelling-api",
    )


app.include_router(stories_router)
