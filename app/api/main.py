from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.db.session import engine
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


@app.exception_handler(OperationalError)
async def database_unavailable_handler(
    request: Request,
    exc: OperationalError,
) -> JSONResponse:
    """Return a controlled response when a database operation fails."""
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        detail = (
            "Database temporarily unavailable. "
            "If this was a write request, verify the story version "
            "before retrying because the commit outcome may be unknown."
        )
    else:
        detail = "Database temporarily unavailable."

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": detail},
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
    """Check whether the API can reach its authoritative database."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable; service is not ready.",
        ) from exc

    return HealthResponse(
        status="ready",
        service="storytelling-api",
    )


app.include_router(stories_router)
