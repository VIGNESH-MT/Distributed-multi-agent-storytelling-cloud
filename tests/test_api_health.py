from fastapi.testclient import TestClient

from app.api.main import APP_VERSION, app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "storytelling-api",
        "version": "0.1.1",
    }
    assert response.json()["version"] == APP_VERSION


def test_liveness_endpoint():
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_readiness_endpoint():
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_openapi_documentation_available():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert (
        response.json()["info"]["title"]
        == "Distributed Multi-Agent Storytelling Cloud"
    )
    assert response.json()["info"]["version"] == APP_VERSION
