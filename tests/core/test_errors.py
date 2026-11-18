import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import INTERNAL_ERROR_DETAIL

INTERNAL_MESSAGE = "internal detail that must not reach the client"


@pytest.fixture
def failing_client(app: FastAPI) -> TestClient:
    def boom() -> None:
        raise RuntimeError(INTERNAL_MESSAGE)

    app.add_api_route("/boom", boom)
    # Starlette re-raises after the handler runs; ask TestClient to return the response.
    return TestClient(app, raise_server_exceptions=False)


def test_unexpected_error_returns_generic_500(failing_client: TestClient) -> None:
    response = failing_client.get("/boom?email=student@example.com")

    assert response.status_code == 500
    assert response.json() == {"detail": INTERNAL_ERROR_DETAIL}
    assert INTERNAL_MESSAGE not in response.text


def test_unexpected_error_is_logged_without_query_string(
    failing_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="app.core.errors"):
        failing_client.get("/boom?email=student@example.com")

    assert "GET /boom" in caplog.text
    assert "student@example.com" not in caplog.text


def test_http_errors_keep_default_handling(client: TestClient) -> None:
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
