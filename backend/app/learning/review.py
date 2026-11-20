"""Spaced review (Step 23b): when each attempted lesson should be revisited.

Pure: a lesson's graded attempts (time, passed) go in, its schedule comes out, so every
rule is testable with fixed times. Nothing is stored; the schedule is replayed from the
attempts on each request.

Rules:
- The first attempt (pass or fail) schedules the lesson 1 day later.
- A pass made when the lesson is due moves it up the ladder (1 → 3 → 7 → 14 → 30 days);
  a pass at the 30-day step marks it mastered, and it stops coming up.
- A pass before the lesson is due changes nothing: otherwise passing five times in ten
  minutes would climb the whole ladder and skip the spacing.
- A failed attempt always resets the lesson to 1 day, mastered or not.
- "Due" counts 24-hour periods from the attempt: students' time zones are unknown.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

LADDER_DAYS = (1, 3, 7, 14, 30)


@dataclass(frozen=True)
class Attempt:
    at: datetime
    passed: bool


@dataclass(frozen=True)
class LessonReview:
    lesson_id: str
    step: int  # index into LADDER_DAYS of the current wait
    due_at: datetime | None  # None once mastered
    mastered: bool

    @property
    def interval_days(self) -> int:
        return LADDER_DAYS[self.step]

    def is_due(self, now: datetime) -> bool:
        return self.due_at is not None and now >= self.due_at


def schedule(lesson_id: str, attempts: Iterable[Attempt]) -> LessonReview | None:
    """The lesson's schedule after its attempts (any order); None if it has none."""
    review: LessonReview | None = None
    for attempt in sorted(attempts, key=lambda a: a.at):
        review = _after(review, lesson_id, attempt)
    return review


def _after(review: LessonReview | None, lesson_id: str, attempt: Attempt) -> LessonReview:
    if review is None or not attempt.passed:
        return _at_step(lesson_id, 0, attempt.at)
    if review.mastered or not review.is_due(attempt.at):
        return review  # early pass, or already mastered: nothing changes
    if review.step == len(LADDER_DAYS) - 1:
        return LessonReview(lesson_id, review.step, due_at=None, mastered=True)
    return _at_step(lesson_id, review.step + 1, attempt.at)


def _at_step(lesson_id: str, step: int, at: datetime) -> LessonReview:
    return LessonReview(lesson_id, step, at + timedelta(days=LADDER_DAYS[step]), mastered=False)


def review_schedule(attempts_by_lesson: Mapping[str, Sequence[Attempt]]) -> list[LessonReview]:
    """Every attempted lesson's schedule, soonest due first; mastered lessons last."""
    reviews = [
        review
        for lesson_id, attempts in attempts_by_lesson.items()
        if (review := schedule(lesson_id, attempts)) is not None
    ]
    return sorted(reviews, key=_order)


def _order(review: LessonReview) -> tuple[bool, float, str]:
    # Mastered lessons have no due time; they sort last by the first field anyway.
    due = review.due_at.timestamp() if review.due_at else 0.0
    return (review.mastered, due, review.lesson_id)
