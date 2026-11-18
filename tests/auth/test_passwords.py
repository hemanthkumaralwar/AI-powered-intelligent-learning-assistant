import argon2
import pytest

from app.auth.passwords import PasswordHasher

pytestmark = pytest.mark.anyio


@pytest.fixture
def hasher() -> PasswordHasher:
    # Minimal cost keeps tests fast; production uses argon2's secure defaults.
    return PasswordHasher(argon2.PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))


async def test_hash_is_argon2id_and_never_the_password(hasher: PasswordHasher) -> None:
    hashed = await hasher.hash("correct horse battery")

    assert hashed.startswith("$argon2id$")
    assert "correct horse battery" not in hashed


async def test_same_password_hashes_differently(hasher: PasswordHasher) -> None:
    assert await hasher.hash("same-password") != await hasher.hash("same-password")


async def test_verify_accepts_right_and_rejects_wrong(hasher: PasswordHasher) -> None:
    hashed = await hasher.hash("right-password")

    assert await hasher.verify(hashed, "right-password") is True
    assert await hasher.verify(hashed, "wrong-password") is False


@pytest.mark.parametrize("bad_hash", ["", "not-a-hash", "$argon2id$v=19$broken"])
async def test_verify_treats_corrupt_hashes_as_mismatch(
    hasher: PasswordHasher, bad_hash: str
) -> None:
    assert await hasher.verify(bad_hash, "anything") is False


async def test_long_passwords_are_not_truncated(hasher: PasswordHasher) -> None:
    # bcrypt would ignore everything after 72 bytes; argon2 must not.
    base = "x" * 100
    hashed = await hasher.hash(base + "A")

    assert await hasher.verify(hashed, base + "B") is False


async def test_burn_time_runs_without_error(hasher: PasswordHasher) -> None:
    await hasher.burn_time("whatever")


def test_default_hasher_uses_secure_parameters() -> None:
    hashed = argon2.PasswordHasher().hash("x")

    assert "$argon2id$" in hashed
    assert argon2.extract_parameters(hashed).memory_cost >= 19 * 1024
