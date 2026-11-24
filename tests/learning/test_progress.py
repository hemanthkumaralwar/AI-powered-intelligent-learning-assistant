"""Scoring and recommendation rules (pure functions, no database)."""

import pytest

from app.learning.progress import (
    ExerciseInfo,
    LessonInfo,
    ModuleInfo,
    compute_progress,
    exercise_score,
)
from app.learning.recommend import MAX_RECOMMENDATIONS, recommend


def lesson(lesson_id: str, *exercise_ids: str) -> LessonInfo:
    return LessonInfo(
        lesson_id,
        lesson_id.title(),
        tuple(ExerciseInfo(e, f"Exercise {e}", "bug_hunt") for e in exercise_ids),
    )


# Three modules of two lessons, two exercises each.
COURSE = [
    ModuleInfo("m1", "Basics", (lesson("l1", "e1", "e2"), lesson("l2", "e3", "e4"))),
    ModuleInfo("m2", "Functions", (lesson("l3", "e5", "e6"), lesson("l4", "e7", "e8"))),
    ModuleInfo("m3", "Arrays", (lesson("l5", "e9", "e10"), lesson("l6", "e11", "e12"))),
]


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ([True], 1.0),
        ([False], 0.0),
        ([True, False, False, False], 8 / 15),  # recovered after three failures
        ([False, True], 1 / 3),  # passed before, failed most recently
        ([], 0.0),
    ],
)
def test_exercise_score_weights_recent_attempts(results: list[bool], expected: float) -> None:
    assert exercise_score(results) == pytest.approx(expected)


def test_untouched_lessons_are_not_started_not_zero() -> None:
    (basics, functions, arrays) = compute_progress(COURSE, {"e1": [True], "e2": [False]})

    assert basics.lessons[0].mastery == 0.5
    assert basics.lessons[1].mastery is None and not basics.lessons[1].started
    assert (basics.mastery, basics.coverage) == (0.5, 0.5)
    assert (functions.mastery, functions.coverage) == (None, 0.0)


def test_module_mastery_averages_started_lessons() -> None:
    attempts = {"e1": [True], "e3": [True], "e4": [False]}

    (basics, _, _) = compute_progress(COURSE, attempts)

    assert basics.mastery == pytest.approx((1.0 + 0.5) / 2)
    assert basics.coverage == 1.0


def test_new_student_starts_at_the_beginning() -> None:
    picks = recommend(compute_progress(COURSE, {}), weak_threshold=0.6)

    assert [p.progress.lesson.id for p in picks] == ["l1", "l2", "l3", "l4", "l5"]
    assert {p.kind for p in picks} == {"next"}
    assert len(picks) == MAX_RECOMMENDATIONS


def test_weak_lessons_come_first_weakest_first_then_the_next_lessons() -> None:
    attempts = {
        "e1": [True],
        "e2": [True],  # l1: 1.0
        "e3": [False, True],
        "e4": [True],  # l2: (1/3 + 1)/2 = 0.67
        "e5": [False],
        "e6": [True, False],  # l3: (0 + 2/3)/2 = 0.33 weak
        "e9": [False],
        "e10": [False],  # l5: 0.0 weak (furthest started)
    }

    picks = recommend(compute_progress(COURSE, attempts), weak_threshold=0.6)

    assert [(p.kind, p.progress.lesson.id) for p in picks] == [
        ("review", "l5"),
        ("review", "l3"),
        ("next", "l6"),  # after the furthest started lesson; l4 (skipped) is not "next"
    ]
    assert picks[0].reason == "Review: 0% on this lesson's exercises"
    # Review lists only exercises still under the threshold, with their scores.
    assert [(e.exercise.id, e.score) for e in picks[1].exercises] == [("e5", 0.0)]


def test_unattempted_exercises_of_a_weak_lesson_are_listed_too() -> None:
    picks = recommend(compute_progress(COURSE, {"e1": [False]}), weak_threshold=0.6)

    assert [(e.exercise.id, e.score) for e in picks[0].exercises] == [("e1", 0.0), ("e2", None)]


def test_finished_course_recommends_nothing() -> None:
    every = {f"e{n}": [True] for n in range(1, 13)}

    assert recommend(compute_progress(COURSE, every), weak_threshold=0.6) == []


def test_threshold_and_limit_are_respected() -> None:
    progress = compute_progress(COURSE, {"e1": [True, False], "e2": [True]})  # l1 = 0.83

    assert recommend(progress, weak_threshold=0.9)[0].kind == "review"
    assert recommend(progress, weak_threshold=0.6)[0].kind == "next"
    assert len(recommend(progress, weak_threshold=0.6, limit=2)) == 2


# ---- Lesson quiz scores count next to exercises -------------------------------------


@pytest.mark.parametrize(
    ("scores", "expected"),
    [
        ([0.7], 0.7),
        ([1.0, 0.4], (1.0 + 0.5 * 0.4) / 1.5),  # a retake counts most
        ([0.2, 1.0, 1.0], (0.2 + 0.5 + 0.25) / 1.75),
    ],
)
def test_quiz_score_weights_recent_attempts(scores: list[float], expected: float) -> None:
    (basics, _, _) = compute_progress(COURSE, {}, {"l1": scores})

    assert basics.lessons[0].quiz_score == pytest.approx(expected)
    assert basics.lessons[0].mastery == pytest.approx(expected)


def test_taking_the_quiz_starts_a_lesson() -> None:
    (basics, _, _) = compute_progress(COURSE, {}, {"l2": [0.5]})

    assert basics.lessons[1].started and basics.lessons[1].exercise_scores == {}
    assert basics.coverage == 0.5


def test_quiz_counts_as_one_item_next_to_the_exercises() -> None:
    (basics, _, _) = compute_progress(COURSE, {"e1": [True], "e2": [False]}, {"l1": [0.3]})

    assert basics.lessons[0].mastery == pytest.approx((1.0 + 0.0 + 0.3) / 3)


def test_a_poor_quiz_makes_a_lesson_weak_and_says_why() -> None:
    picks = recommend(compute_progress(COURSE, {}, {"l1": [0.4]}), weak_threshold=0.6)

    assert (picks[0].kind, picks[0].progress.lesson.id) == ("review", "l1")
    assert picks[0].reason == "Review: 40% on this lesson's quiz"


def test_review_reason_names_the_quiz_and_the_exercises() -> None:
    progress = compute_progress(COURSE, {"e1": [True], "e2": [False]}, {"l1": [0.2]})

    (pick, *_) = recommend(progress, weak_threshold=0.6)

    assert pick.reason == "Review: 40% (quiz 20%, exercises 50%)"


def test_a_good_quiz_can_lift_a_lesson_out_of_review() -> None:
    exercises = {"e1": [True], "e2": [False]}  # 0.5 on its own: weak

    with_quiz = recommend(compute_progress(COURSE, exercises, {"l1": [1.0]}), 0.6)
    without = recommend(compute_progress(COURSE, exercises), 0.6)

    assert without[0].kind == "review"
    assert with_quiz[0].kind == "next"  # (1 + 0 + 1) / 3 = 0.67
