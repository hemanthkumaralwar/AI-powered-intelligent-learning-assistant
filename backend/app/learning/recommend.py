"""What to do next: review weak lessons first (from exercise and quiz results), then
continue the course (pure functions)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.learning.progress import ExerciseInfo, LessonProgress, ModuleProgress

MAX_RECOMMENDATIONS = 5


@dataclass(frozen=True)
class ExerciseToDo:
    exercise: ExerciseInfo
    # None: never attempted.
    score: float | None


@dataclass(frozen=True)
class Recommendation:
    kind: Literal["review", "next"]
    progress: LessonProgress
    reason: str
    # Review: the exercises not yet mastered. Next: all of the lesson's exercises.
    exercises: tuple[ExerciseToDo, ...]


def recommend(
    modules: Sequence[ModuleProgress], weak_threshold: float, limit: int = MAX_RECOMMENDATIONS
) -> list[Recommendation]:
    """Weak lessons (mastery under `weak_threshold`) weakest first, then the first lessons
    not yet started after the furthest one the student has worked on."""
    lessons = [lesson for module in modules for lesson in module.lessons]
    reviews = sorted(
        (lesson for lesson in lessons if lesson.started and lesson.mastery < weak_threshold),
        key=lambda lesson: lesson.mastery,
    )
    picks = [_review(lesson, weak_threshold) for lesson in reviews]
    picks += [_next(lesson) for lesson in _continue_from(lessons)]
    return picks[:limit]


def _continue_from(lessons: Sequence[LessonProgress]) -> list[LessonProgress]:
    """Not-started lessons after the furthest started one (or from the beginning)."""
    furthest = max((i for i, lesson in enumerate(lessons) if lesson.started), default=-1)
    return [lesson for lesson in lessons[furthest + 1 :] if not lesson.started]


def _review(lesson: LessonProgress, weak_threshold: float) -> Recommendation:
    to_do = tuple(
        ExerciseToDo(exercise, lesson.exercise_scores.get(exercise.id))
        for exercise in lesson.lesson.exercises
        if lesson.exercise_scores.get(exercise.id, 0.0) < weak_threshold
    )
    return Recommendation("review", lesson, _review_reason(lesson), to_do)


def _review_reason(lesson: LessonProgress) -> str:
    """Where the low score comes from: the exercises, the quiz, or both."""
    if lesson.quiz_score is None:
        return f"Review: {lesson.mastery:.0%} on this lesson's exercises"
    if not lesson.exercise_scores:
        return f"Review: {lesson.quiz_score:.0%} on this lesson's quiz"
    exercises = sum(lesson.exercise_scores.values()) / len(lesson.exercise_scores)
    return f"Review: {lesson.mastery:.0%} (quiz {lesson.quiz_score:.0%}, exercises {exercises:.0%})"


def _next(lesson: LessonProgress) -> Recommendation:
    to_do = tuple(ExerciseToDo(exercise, None) for exercise in lesson.lesson.exercises)
    return Recommendation("next", lesson, "Next in the course", to_do)
