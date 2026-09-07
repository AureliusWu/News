from fastapi.testclient import TestClient

from app.main import app


def test_health_route() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"healthy", "degraded"}
    assert payload["app_name"] == "Global News"
