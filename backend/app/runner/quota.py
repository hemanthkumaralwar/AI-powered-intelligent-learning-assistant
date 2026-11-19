"""Run quotas: per student (minute and day) and for the whole app (minute).

All runs leave Render from one IP, so the free runners' per-IP allowance is shared by
every student; the app-wide limit protects it.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from app.core.quota import DAY, MINUTE, Quota, QuotaRule


@dataclass(frozen=True)
class QuotaLimits:
    per_user_per_minute: int
    per_user_per_day: int
    global_per_minute: int


class RunQuota(Quota):
    def __init__(self, limits: QuotaLimits, clock: Callable[[], float] = time.monotonic) -> None:
        super().__init__(
            [
                QuotaRule(
                    "You are running code too often; wait a moment.",
                    limits.per_user_per_minute,
                    MINUTE,
                ),
                QuotaRule(
                    "You have reached today's limit for running code.",
                    limits.per_user_per_day,
                    DAY,
                ),
                QuotaRule(
                    "The code runner is busy; try again in a moment.",
                    limits.global_per_minute,
                    MINUTE,
                    per_user=False,
                ),
            ],
            clock,
        )
