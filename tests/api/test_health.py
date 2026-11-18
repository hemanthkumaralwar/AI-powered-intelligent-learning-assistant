from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_exposes_no_internal_details(client: TestClient) -> None:
    assert set(client.get("/health").json()) == {"status"}


def test_health_rejects_other_methods(client: TestClient) -> None:
    assert client.post("/health").status_code == 405
