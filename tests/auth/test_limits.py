import pytest

from app.auth.limits import FAILURE_WINDOW, LoginGuard
from app.core.quota import QuotaExceededError


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def guard(clock: Clock, failures: int = 3, logins: int = 100, registrations: int = 2):
    return LoginGuard(
        failures_per_username=failures,
        logins_per_minute=logins,
        registrations_per_minute=registrations,
        clock=clock,
    )


def test_repeated_failures_lock_that_username_only() -> None:
    clock = Clock()
    login = guard(clock)
    for _ in range(3):
        login.check_login("Asha")
        login.record_failure("asha ")

    with pytest.raises(QuotaExceededError, match="failed sign-ins") as excinfo:
        login.check_login("ASHA")  # usernames are case-insensitive
    assert 0 < excinfo.value.retry_after <= FAILURE_WINDOW
    login.check_login("ravi")  # another account is unaffected


def test_lock_lifts_after_the_window() -> None:
    clock = Clock()
    login = guard(clock, failures=1)
    login.record_failure("asha")

    clock.now += FAILURE_WINDOW + 1

    login.check_login("asha")


def test_app_wide_login_and_registration_caps() -> None:
    clock = Clock()
    limits = guard(clock, logins=2, registrations=1)
    limits.check_login("a")
    limits.check_login("b")
    with pytest.raises(QuotaExceededError, match="Too many sign-ins"):
        limits.check_login("c")

    limits.check_registration()
    with pytest.raises(QuotaExceededError, match="Too many new accounts"):
        limits.check_registration()
