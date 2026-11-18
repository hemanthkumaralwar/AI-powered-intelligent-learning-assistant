import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, SecretStr

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


class Signup(BaseModel):
    username: str = Field(min_length=3)
    password: SecretStr = Field(min_length=8)


@pytest.fixture
def validating_client(app: FastAPI) -> TestClient:
    async def signup(body: Signup) -> dict:
        return {"ok": True}

    app.add_api_route("/signup", signup, methods=["POST"])
    return TestClient(app)


def test_validation_errors_never_echo_input(validating_client: TestClient) -> None:
    response = validating_client.post("/signup", json={"username": "qz", "password": "abc12"})

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert all(set(error) == {"loc", "msg", "type"} for error in errors)
    assert "qz" not in response.text and "abc12" not in response.text


def test_password_errors_do_not_reveal_length(validating_client: TestClient) -> None:
    response = validating_client.post("/signup", json={"username": "valid-name", "password": "abc"})

    (error,) = response.json()["detail"]
    assert error == {
        "loc": ["body", "password"],
        "msg": "Invalid value",
        "type": "too_short",
    }


def test_other_validation_messages_are_kept(validating_client: TestClient) -> None:
    response = validating_client.post("/signup", json={"username": "ab", "password": "long-enough"})

    (error,) = response.json()["detail"]
    assert error["msg"].startswith("String should have at least 3 characters")
