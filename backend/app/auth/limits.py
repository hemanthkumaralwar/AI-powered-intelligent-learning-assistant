"""Brute-force protection for login and registration (in memory, like the other quotas).

Failed logins are counted per username, so guessing one account's password is slow no
matter how many machines try. There is no per-IP limit: behind Render's proxy many
clients can share an address, and one noisy student must not lock out a classroom. An
app-wide cap on logins and registrations bounds the total load and password hashing.
"""

import time
from collections.abc import Callable

from app.core.quota import MINUTE, Quota, QuotaExceededError, QuotaRule, SlidingWindow
from app.db.repositories.users import normalize_username

FAILURE_WINDOW = 15 * MINUTE


class LoginGuard:
    def __init__(
        self,
        *,
        failures_per_username: int,
        logins_per_minute: int,
        registrations_per_minute: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._failures = SlidingWindow(failures_per_username, FAILURE_WINDOW)
        self._logins = Quota(
            [
                QuotaRule(
                    "Too many sign-ins right now; try again shortly.",
                    logins_per_minute,
                    MINUTE,
                    per_user=False,
                )
            ],
            clock,
        )
        self._registrations = Quota(
            [
                QuotaRule(
                    "Too many new accounts right now; try again shortly.",
                    registrations_per_minute,
                    MINUTE,
                    per_user=False,
                )
            ],
            clock,
        )

    def check_login(self, username: str) -> None:
        """Raise `QuotaExceededError` if this account is locked or the app is busy."""
        wait = self._failures.wait_time(normalize_username(username), self._clock())
        if wait > 0:
            # Same wording whether or not the account exists: no account enumeration.
            raise QuotaExceededError(
                "Too many failed sign-ins for this account; try again later.", retry_after=wait
            )
        self._logins.consume("*")

    def record_failure(self, username: str) -> None:
        self._failures.record(normalize_username(username), self._clock())

    def check_registration(self) -> None:
        self._registrations.consume("*")
