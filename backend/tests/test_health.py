from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import health


def test_health_route() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"healthy", "degraded"}
    assert payload["app_name"] == "Global News"


def test_ready_when_db_connected(monkeypatch) -> None:
    async def _connected() -> bool:
        return True

    monkeypatch.setattr(health, "db_health", _connected)

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["database_connected"] is True


def test_ready_when_db_disconnected(monkeypatch) -> None:
    async def _disconnected() -> bool:
        return False

    monkeypatch.setattr(health, "db_health", _disconnected)

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["database_connected"] is False


def test_cors_config_no_wildcard() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"Origin": "https://example.com"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
