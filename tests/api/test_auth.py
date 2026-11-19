"""Auth endpoints end to end against a real (Neon test branch) database schema."""

import logging
from collections.abc import AsyncIterator
from datetime import timedelta

import argon2
import httpx2
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from app.api.deps import AdminUser, CurrentUser
from app.auth.passwords import PasswordHasher
from app.auth.seed import seed_admin
from app.auth.service import AuthService
from app.auth.tokens import TokenService
from app.core.config import Settings
from app.db.errors import DuplicateError
from app.db.models import User
from app.db.repositories.users import UserRepository
from app.db.session import Database
from app.main import create_app

pytestmark = pytest.mark.anyio

PASSWORD = "Str0ng-Passphrase!"  # noqa: S105 - test fixture value
JWT_SECRET = "j" * 64


def fast_auth(ttl: timedelta = timedelta(minutes=60)) -> AuthService:
    hasher = PasswordHasher(argon2.PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))
    return AuthService(hasher, TokenService(JWT_SECRET, ttl))


def build_app(database: Database, auth: AuthService | None = None, **settings) -> FastAPI:
    app = create_app(
        Settings(
            _env_file=None,
            environment="test",
            log_level="WARNING",
            embedding_provider="fake",
            embedding_document_texts_per_minute=100_000,
            embedding_query_texts_per_minute=100_000,
            **settings,
        ),
        database=database,
        auth=auth or fast_auth(),
    )

    # Test-only routes: real admin endpoints arrive in Step 7.
    @app.get("/test/admin-only")
    async def admin_only(user: AdminUser) -> dict:
        return {"admin": user.username}

    @app.get("/test/any-user")
    async def any_user(user: CurrentUser) -> dict:
        return {"user": user.username}

    return app


@pytest.fixture
async def client(database: Database) -> AsyncIterator[httpx2.AsyncClient]:
    app = build_app(database)
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http


async def register(client: httpx2.AsyncClient, username: str = "asha") -> httpx2.Response:
    return await client.post("/auth/register", json={"username": username, "password": PASSWORD})


async def login_token(client: httpx2.AsyncClient, username: str = "asha") -> str:
    response = await client.post("/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def make_admin(database: Database, auth: AuthService | None = None) -> None:
    await seed_admin(database, auth or fast_auth(), "admin", SecretStr(PASSWORD))


# ---- register / login / me -----------------------------------------------------------


async def test_register_login_me_round_trip(client: httpx2.AsyncClient) -> None:
    created = await register(client, "  Asha  ")
    assert created.status_code == 201
    assert created.json()["username"] == "asha"
    assert created.json()["role"] == "student"
    assert set(created.json()) == {"id", "username", "role"}

    login = await client.post("/auth/login", json={"username": "ASHA", "password": PASSWORD})
    assert login.status_code == 200
    body = login.json()
    assert (body["token_type"], body["expires_in"]) == ("bearer", 3600)

    me = await client.get("/auth/me", headers=bearer(body["access_token"]))
    assert me.json() == created.json()


async def test_duplicate_username_is_409(client: httpx2.AsyncClient) -> None:
    await register(client, "ravi")

    response = await register(client, "RAVI")

    assert response.status_code == 409
    assert response.json() == {"detail": "Username already taken"}


@pytest.mark.parametrize(
    "body",
    [
        {"username": "zq", "password": PASSWORD},
        {"username": "has space", "password": PASSWORD},
        {"username": "x" * 51, "password": PASSWORD},
        {"username": "user-qzx", "password": "qz5ab"},
        {"username": "user-qzx", "password": "p" * 129},
        {"username": "user-qzx"},
    ],
    ids=["too-short", "bad-chars", "too-long", "weak-password", "huge-password", "missing"],
)
async def test_invalid_registration_is_422_without_echoing_input(
    client: httpx2.AsyncClient, body: dict
) -> None:
    response = await client.post("/auth/register", json=body)

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert all(set(error) == {"loc", "msg", "type"} for error in errors)
    for value in body.values():
        assert value not in response.text
    # Password errors must not reveal the submitted length either.
    password_errors = [e for e in errors if "password" in e["loc"]]
    assert all(e["msg"] == "Invalid value" for e in password_errors)


async def test_wrong_password_and_unknown_user_look_identical(client: httpx2.AsyncClient) -> None:
    await register(client, "asha")

    wrong = await client.post("/auth/login", json={"username": "asha", "password": "nope-nope"})
    unknown = await client.post("/auth/login", json={"username": "ghost", "password": PASSWORD})

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Invalid username or password"}
    assert wrong.headers["www-authenticate"] == "Bearer"


# ---- tokens and roles ----------------------------------------------------------------


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer garbage"}, {"Authorization": "Basic YWRtaW46cGFzcw=="}],
    ids=["missing", "garbage", "wrong-scheme"],
)
async def test_bad_or_missing_token_is_401(client: httpx2.AsyncClient, headers: dict) -> None:
    response = await client.get("/auth/me", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_expired_token_is_401(database: Database) -> None:
    app = build_app(database, auth=fast_auth(ttl=timedelta(seconds=-1)))
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://test") as http:
            await register(http)
            token = await login_token(http)
            response = await http.get("/auth/me", headers=bearer(token))

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired token"}


async def test_student_is_forbidden_from_admin_routes(client: httpx2.AsyncClient) -> None:
    await register(client)
    token = await login_token(client)

    assert (await client.get("/test/any-user", headers=bearer(token))).status_code == 200
    forbidden = await client.get("/test/admin-only", headers=bearer(token))
    assert forbidden.status_code == 403
    assert forbidden.json() == {"detail": "Admin access required"}


async def test_admin_can_use_admin_and_user_routes(
    client: httpx2.AsyncClient, database: Database
) -> None:
    await make_admin(database)
    token = await login_token(client, "admin")

    assert (await client.get("/test/admin-only", headers=bearer(token))).json() == {
        "admin": "admin"
    }
    assert (await client.get("/test/any-user", headers=bearer(token))).status_code == 200


async def test_deleted_users_token_stops_working(
    client: httpx2.AsyncClient, database: Database
) -> None:
    user_id = (await register(client)).json()["id"]
    token = await login_token(client)
    async with database.session() as session:
        await session.delete(await session.get(User, user_id))

    assert (await client.get("/auth/me", headers=bearer(token))).status_code == 401


# ---- admin seeding --------------------------------------------------------------------


async def test_admin_seeding_is_idempotent_and_never_promotes(database: Database) -> None:
    auth = fast_auth()
    assert await seed_admin(database, auth, "admin", SecretStr(PASSWORD)) is True
    assert await seed_admin(database, auth, "admin", SecretStr("another-password")) is False

    async with database.session() as session:
        await auth.register(session, "student1", PASSWORD)
    assert await seed_admin(database, auth, "student1", SecretStr(PASSWORD)) is False

    async with database.session() as session:
        users = UserRepository(session)
        admin = await users.get_by_username("admin")
        student = await users.get_by_username("student1")
        await auth.login(session, "admin", PASSWORD)  # the first password still works

    assert admin is not None and admin.role == "admin"
    assert student is not None and student.role == "student"


async def test_startup_seeds_admin_from_settings(database: Database) -> None:
    app = build_app(database, admin_username="Boss", admin_password=PASSWORD)
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://test") as http:
            token = await login_token(http, "boss")
            me = await http.get("/auth/me", headers=bearer(token))

    assert me.json()["role"] == "admin"


# ---- secrets stay secret --------------------------------------------------------------


async def test_password_never_appears_in_responses_or_logs(
    client: httpx2.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        responses = [
            await register(client, "asha"),
            await register(client, "asha"),
            await client.post("/auth/login", json={"username": "asha", "password": PASSWORD}),
            await client.post("/auth/login", json={"username": PASSWORD, "password": PASSWORD}),
        ]
        token = responses[2].json()["access_token"]
        responses.append(await client.get("/auth/me", headers=bearer(token)))

    for response in responses:
        assert PASSWORD not in response.text
    assert PASSWORD not in caplog.text
    assert token not in caplog.text
    assert "login failed" in caplog.text


async def test_seeding_tolerates_a_concurrent_instance(database: Database) -> None:
    class RacingAuth:
        """Another instance inserts the admin between our check and our insert."""

        async def register(self, *args: object, **kwargs: object) -> None:
            raise DuplicateError("username already exists")

    assert await seed_admin(database, RacingAuth(), "admin", SecretStr(PASSWORD)) is False
