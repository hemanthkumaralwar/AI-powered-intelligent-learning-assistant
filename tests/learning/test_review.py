from datetime import UTC, datetime, timedelta

from app.learning.review import LADDER_DAYS, Attempt, review_schedule, schedule

T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
DAY = timedelta(days=1)


def at(days: float, passed: bool) -> Attempt:
    return Attempt(T0 + timedelta(days=days), passed)


def test_no_attempts_no_schedule() -> None:
    assert schedule("l1", []) is None


def test_a_failed_attempt_is_due_24_hours_later() -> None:
    review = schedule("l1", [at(0, False)])

    assert (review.step, review.due_at, review.mastered) == (0, T0 + DAY, False)
    assert not review.is_due(T0 + DAY - timedelta(seconds=1))
    assert review.is_due(T0 + DAY)


def test_a_first_pass_also_comes_back_after_a_day() -> None:
    assert schedule("l1", [at(0, True)]).due_at == T0 + DAY


def test_a_pass_when_due_moves_up_the_ladder() -> None:
    review = schedule("l1", [at(0, True), at(1, True)])

    assert (review.step, review.interval_days) == (1, 3)
    assert review.due_at == T0 + DAY + 3 * DAY


def test_an_early_pass_changes_nothing() -> None:
    once = schedule("l1", [at(0, True)])
    spammed = schedule("l1", [at(0, True), at(0.01, True), at(0.5, True), at(0.9, True)])

    assert spammed == once


def test_the_whole_ladder_then_mastered() -> None:
    attempts = [at(0, True)]
    day = 0
    for wait in LADDER_DAYS:
        day += wait
        attempts.append(at(day, True))

    review = schedule("l1", attempts)

    assert review.mastered and review.due_at is None and not review.is_due(T0 + 1000 * DAY)
    assert schedule("l1", attempts[:-1]).interval_days == 30  # one step before: 30 days


def test_a_failure_resets_even_after_mastery() -> None:
    attempts = [at(0, True)]
    day = 0
    for wait in LADDER_DAYS:
        day += wait
        attempts.append(at(day, True))
    attempts.append(at(day + 5, False))

    review = schedule("l1", attempts)

    assert (review.mastered, review.step, review.due_at) == (False, 0, T0 + (day + 6) * DAY)


def test_a_failure_mid_ladder_resets_to_one_day() -> None:
    review = schedule("l1", [at(0, True), at(1, True), at(4, True), at(5, False)])

    assert (review.step, review.due_at) == (0, T0 + 6 * DAY)


def test_attempts_are_replayed_in_time_order() -> None:
    forwards = [at(0, False), at(1, True)]

    assert schedule("l1", reversed(forwards)) == schedule("l1", forwards)


def test_the_schedule_lists_soonest_due_first_and_mastered_last() -> None:
    mastered = [at(0, True)]
    day = 0
    for wait in LADDER_DAYS:
        day += wait
        mastered.append(at(day, True))

    reviews = review_schedule(
        {"later": [at(5, False)], "sooner": [at(1, False)], "done": mastered, "none": []}
    )

    assert [r.lesson_id for r in reviews] == ["sooner", "later", "done"]
