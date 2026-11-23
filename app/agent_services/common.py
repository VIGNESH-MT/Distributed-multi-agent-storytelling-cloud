"""Shared application setup for independent storytelling agent services."""

from fastapi import FastAPI


def create_agent_app(service_name: str) -> FastAPI:
    app = FastAPI(
        title=service_name,
        description="Independent agent service for the distributed storytelling system.",
        version="0.1.0",
    )

    @app.get("/health/live")
    def liveness():
        return {"status": "alive", "service": service_name}

    @app.get("/health/ready")
    def readiness():
        return {"status": "ready", "service": service_name}

    return app
