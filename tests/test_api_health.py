from fastapi.testclient import TestClient

from app.api.main import APP_VERSION, app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "storytelling-api",
        "version": APP_VERSION,
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


def test_readiness_returns_503_when_database_is_unavailable(monkeypatch):
    from sqlalchemy.exc import OperationalError

    def fail_database_connection():
        raise OperationalError(
            "SELECT 1",
            {},
            Exception("simulated database connection failure"),
        )

    monkeypatch.setattr(
        "app.api.main.engine.connect",
        fail_database_connection,
    )

    readiness_response = client.get("/health/ready")
    liveness_response = client.get("/health/live")

    assert readiness_response.status_code == 503
    assert readiness_response.json()["detail"] == (
        "Database unavailable; service is not ready."
    )

    assert liveness_response.status_code == 200
    assert liveness_response.json()["status"] == "alive"

def test_story_request_returns_503_on_database_failure(monkeypatch):
    from sqlalchemy.exc import OperationalError
    from app.api.routes.stories import get_db

    def failing_get_db():
        raise OperationalError(
            "SELECT",
            {},
            Exception("simulated database connection failure"),
        )
        yield

    monkeypatch.setitem(
        app.dependency_overrides,
        get_db,
        failing_get_db,
    )

    response = client.post(
        "/stories",
        json={
            "title": "CAP failure test",
            "initial_content": "Initial story",
        },
    )

    assert response.status_code == 503
    assert "Database temporarily unavailable" in response.json()["detail"]
    assert "commit outcome may be unknown" in response.json()["detail"]

