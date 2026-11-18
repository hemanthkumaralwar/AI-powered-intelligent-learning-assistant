"""Argon2id password hashing (OWASP's first choice; no 72-byte limit like bcrypt)."""

import asyncio

import argon2
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# Hashed once per process; used to spend the same time on unknown usernames.
_DUMMY_PASSWORD = "dummy-password-for-timing-only"  # noqa: S105 - not a credential


class PasswordHasher:
    """Hashes and verifies passwords off the event loop (~50 ms of CPU each)."""

    def __init__(self, hasher: argon2.PasswordHasher | None = None) -> None:
        self._hasher = hasher or argon2.PasswordHasher()
        self._dummy_hash = self._hasher.hash(_DUMMY_PASSWORD)

    async def hash(self, password: str) -> str:
        return await asyncio.to_thread(self._hasher.hash, password)

    async def verify(self, password_hash: str, password: str) -> bool:
        return await asyncio.to_thread(self._verify, password_hash, password)

    async def burn_time(self, password: str) -> None:
        """Verify against a dummy hash so a missing user takes as long as a wrong password."""
        await self.verify(self._dummy_hash, password)

    def _verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
